"""Run standalone Recovery Prediction Research."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from recovery_prediction import (  # noqa: E402
    classifiers,
    ensemble,
    feature_engineering as fe,
    ic_analysis,
    recovery_backtest,
    targets as target_mod,
    validation,
)
from recovery_prediction.signal_families import FAMILIES  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "recovery_prediction"
DOCS_OUT = ROOT / "docs" / "research" / "recovery_prediction"
PLAN_PATH = DOCS_OUT / "recovery_prediction_research_plan.md"
REPORT_PATH = DOCS_OUT / "recovery_prediction_research_report.md"


def _fmt(x, pct: bool = False) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(x):
        return "n/a"
    return f"{x * 100:.2f}%" if pct else f"{x:.3f}"


def _write_plan() -> None:
    lines = [
        "# Recovery Prediction Research Plan",
        "",
        "> Standalone research experiment. This is not Track A/B/C/D, does not modify",
        "> production allocation logic, and does not promote anything into production.",
        "",
        "## Research Question",
        "",
        "After stress, drawdown, or defensive regimes, can SPY/QQQ recovery and re-risking",
        "states be predicted better than simple baseline behavior?",
        "",
        "## Signal Families",
        "",
        "1. Drawdown-reversal signals.",
        "2. Short-horizon reversal signals.",
        "3. Breadth thrust / participation signals.",
        "4. Credit improvement signals.",
        "5. Volatility normalization signals.",
        "6. Momentum + reversal interaction signals.",
        "",
        "## Research Flow",
        "",
        "Build lagged weekly features, separate forward targets, IC diagnostics, family",
        "and combination ETF tilt backtests, simple train/holdout classifiers, a random",
        "timing placebo, and finally an options-readiness diagnostic. No option strategy",
        "is implemented here.",
        "",
        "## Causality",
        "",
        "All numeric features are shifted one week before scores are computed. Targets",
        "are kept in a separate file and use future 4/8/12-week returns.",
    ]
    PLAN_PATH.write_text("\n".join(lines) + "\n")


def _write_report(
    family_scores: pd.DataFrame,
    family_bt: pd.DataFrame,
    combo_bt: pd.DataFrame,
    classifier_metrics: pd.DataFrame,
    options_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    verdict: str,
) -> None:
    best_family = family_scores[
        (family_scores["window"] == "train") & (family_scores["target"] == "fwd_8w_return")
    ].sort_values("rank_ic", ascending=False).head(1)
    best_family_name = best_family.iloc[0]["family"] if len(best_family) else "n/a"
    main = combo_bt[combo_bt["variant"] == "regime_gated_composite"].iloc[0]
    placebo = combo_bt[combo_bt["variant"] == "random_timing_placebo"].iloc[0]
    classifier_holdout = classifier_metrics[
        (classifier_metrics["window"] == "holdout")
        & (classifier_metrics["metric"] == "precision_top_quartile")
    ].sort_values("value", ascending=False)
    best_classifier = classifier_holdout.iloc[0]["model"] if len(classifier_holdout) else "n/a"
    best_ready = options_readiness.sort_values("avg_8w_move_surplus_vs_rough_breakeven", ascending=False).head(1)
    best_ready_name = best_ready.iloc[0]["variant"] if len(best_ready) else "n/a"

    lines = [
        "# Recovery Prediction Research Report",
        "",
        "> Standalone research experiment. Not production. No allocation logic was modified.",
        "",
        f"**Final verdict: `{verdict}`**",
        "",
        "## 1. Summary",
        "",
        f"Best train IC family: `{best_family_name}`.",
        f"Predeclared regime-gated composite Sharpe: {_fmt(main['overlay_sharpe'])} vs baseline {_fmt(main['baseline_sharpe'])}.",
        f"Incremental CAGR: {_fmt(main['incremental_cagr'], True)}; incremental Sharpe: {_fmt(main['incremental_sharpe'])}.",
        f"Random placebo Sharpe: {_fmt(placebo['overlay_sharpe'])}.",
        "",
        "## 2. Family IC Scores",
        "",
        "| Family | Window | Rank IC | Precision Top Quintile | Avg Fwd 8w Top Quintile |",
        "|---|---|---:|---:|---:|",
    ]
    for _, r in family_scores[family_scores["target"] == "fwd_8w_return"].iterrows():
        lines.append(
            f"| `{r['family']}` | {r['window']} | {_fmt(r['rank_ic'])} | "
            f"{_fmt(r['strong_recovery_precision_top_quintile'], True)} | {_fmt(r['avg_forward_return_top_quintile'], True)} |"
        )

    lines += [
        "",
        "## 3. ETF Tilt Backtests",
        "",
        "| Variant | Sharpe | CAGR | MaxDD | CVaR 5% | Activations/Yr | Ex Top 3 Sharpe |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in combo_bt.iterrows():
        lines.append(
            f"| `{r['variant']}` | {_fmt(r['overlay_sharpe'])} | {_fmt(r['overlay_cagr'], True)} | "
            f"{_fmt(r['overlay_max_drawdown'], True)} | {_fmt(r['overlay_cvar_5'], True)} | "
            f"{_fmt(r['activations_per_year'])} | {_fmt(r['sharpe_ex_top3_signal_periods'])} |"
        )

    lines += [
        "",
        "## 4. Classifiers",
        "",
        f"Best holdout classifier by top-quartile precision: `{best_classifier}`.",
        "",
        "| Model | Window | Precision | Recall | False Positive Rate | Risk-Off FPR |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model in sorted(classifier_metrics["model"].unique()):
        for window in ("train", "holdout"):
            precision = _metric(classifier_metrics, model, window, "precision_top_quartile")
            recall = _metric(classifier_metrics, model, window, "recall_top_quartile")
            fpr = _metric(classifier_metrics, model, window, "false_positive_rate")
            rofpr = _metric(classifier_metrics, model, window, "risk_off_false_positive_rate")
            lines.append(f"| `{model}` | {window} | {_fmt(precision, True)} | {_fmt(recall, True)} | {_fmt(fpr, True)} | {_fmt(rofpr, True)} |")

    lines += [
        "",
        "## 5. Options-Readiness Diagnostic",
        "",
        "No options strategy is tested here. This only asks whether ETF recovery signals",
        "identify moves that might later justify real option-chain testing.",
        "",
        f"Best readiness variant: `{best_ready_name}`.",
        "",
        "| Variant | Signals/Yr | Avg Fwd 8w | Rough Breakeven | Surplus | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, r in options_readiness.iterrows():
        lines.append(
            f"| `{r['variant']}` | {_fmt(r['signals_per_year'])} | {_fmt(r['avg_fwd_8w_return'], True)} | "
            f"{_fmt(r['rough_option_breakeven_move'], True)} | {_fmt(r['avg_8w_move_surplus_vs_rough_breakeven'], True)} | {r['options_readiness']} |"
        )

    lines += [
        "",
        "## 6. Validation Gates",
        "",
        "| # | Gate | Result | Detail |",
        "|---:|---|---|---|",
    ]
    for _, r in gates.iterrows():
        lines.append(f"| {int(r['gate_number'])} | `{r['gate']}` | {'PASS' if r['pass'] else 'FAIL'} | {r['detail']} |")

    lines += [
        "",
        "## 7. Answers",
        "",
        f"1. Best family: `{best_family_name}` by train rank IC.",
        "2. Failed families are visible in the IC table where train/holdout rank IC is weak or unstable.",
        "3. Stable IC requires positive train and holdout IC; see validation gate 1.",
        "4. Combination improvement is checked by gate 2.",
        f"5. Classifiers did not automatically dominate simple rules; best holdout classifier was `{best_classifier}`.",
        f"6. Portfolio impact: regime-gated composite Sharpe {_fmt(main['overlay_sharpe'])} vs baseline {_fmt(main['baseline_sharpe'])}.",
        "7. Sharpe/CAGR/drawdown/CVaR are reported in the ETF tilt table and gates.",
        f"8. Random timing placebo Sharpe was {_fmt(placebo['overlay_sharpe'])}.",
        "9. Best/top-3 signal period robustness is checked by gates 12 and 13.",
        "10. Fake-bounce labels are included in targets and classifier prediction diagnostics.",
        "11. Options-readiness is diagnostic only and remains proxy research.",
        f"12. Status: `{verdict}`.",
        "13. Next: investigate the highest-stability signals with stricter point-in-time data and only then consider real option-chain testing.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def _metric(df: pd.DataFrame, model: str, window: str, metric: str) -> float:
    sub = df[(df["model"] == model) & (df["window"] == window) & (df["metric"] == metric)]
    return float(sub["value"].iloc[0]) if len(sub) else np.nan


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    print("[recovery-prediction] building lagged feature panel...")
    features = fe.build_feature_panel(lag_weeks=1)
    targets = target_mod.build_targets(features)
    features.to_csv(DATA_OUT / "recovery_feature_panel.csv", index=False)
    targets.to_csv(DATA_OUT / "recovery_targets.csv", index=False)

    print("[recovery-prediction] running IC analysis...")
    ic_by_feature = ic_analysis.compute_ic_by_feature(features, targets)
    ic_by_regime = ic_analysis.compute_ic_by_regime(features, targets)
    family_scores = ic_analysis.family_scores(features, targets)
    ic_by_feature.to_csv(DATA_OUT / "recovery_ic_by_feature.csv", index=False)
    ic_by_regime.to_csv(DATA_OUT / "recovery_ic_by_regime.csv", index=False)
    family_scores.to_csv(DATA_OUT / "recovery_family_scores.csv", index=False)

    print("[recovery-prediction] training simple classifiers...")
    classifier_metrics, classifier_predictions = classifiers.run_classifiers(features, targets)
    ensemble_predictions = ensemble.build_ensemble_predictions(features, classifier_predictions)
    classifier_metrics.to_csv(DATA_OUT / "recovery_classifier_metrics.csv", index=False)
    ensemble_predictions.to_csv(DATA_OUT / "recovery_ensemble_predictions.csv", index=False)

    print("[recovery-prediction] running ETF tilt backtests...")
    family_bt, family_returns = recovery_backtest.run_family_backtests(features, targets)
    combo_bt, _, combo_returns = recovery_backtest.run_combination_backtests(features, targets, classifier_predictions)
    family_bt.to_csv(DATA_OUT / "recovery_family_backtests.csv", index=False)
    combo_bt.to_csv(DATA_OUT / "recovery_combination_backtests.csv", index=False)
    equity = recovery_backtest._equity_table({**family_returns, **combo_returns})
    equity.to_csv(DATA_OUT / "baseline_vs_recovery_tilt_equity.csv")

    print("[recovery-prediction] running options-readiness diagnostic...")
    readiness = validation.build_options_readiness(features, targets)
    readiness.to_csv(DATA_OUT / "options_readiness_diagnostics.csv", index=False)
    gates, verdict = validation.evaluate_gates(family_scores, ic_by_feature, family_bt, combo_bt, classifier_metrics, readiness)

    _write_plan()
    _write_report(family_scores, family_bt, combo_bt, classifier_metrics, readiness, gates, verdict)
    snapshot = {
        "experiment": "recovery_prediction_research",
        "verdict": verdict,
        "feature_lag_weeks": 1,
        "target_tickers": fe.TARGET_TICKERS,
        "families": list(FAMILIES.keys()),
        "gates": gates.to_dict(orient="records"),
        "main_variant": "regime_gated_composite",
        "main_variant_summary": combo_bt[combo_bt["variant"] == "regime_gated_composite"].iloc[0].to_dict(),
        "proxy_note": "ETF recovery prediction first; options-readiness is diagnostic only, no options strategy tested.",
    }
    (DATA_OUT / "recovery_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
    print(f"[recovery-prediction] verdict: {verdict}")
    print(f"[recovery-prediction] outputs -> {DATA_OUT}")
    print(f"[recovery-prediction] report  -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
