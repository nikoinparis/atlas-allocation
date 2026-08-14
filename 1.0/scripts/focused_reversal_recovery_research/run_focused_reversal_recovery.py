"""Run standalone Focused Reversal Recovery Research."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from focused_reversal_recovery import (  # noqa: E402
    backtest,
    classifier,
    feature_engineering as fe,
    ic_analysis,
    placebo,
    targets as target_mod,
    validation,
)
from focused_reversal_recovery.reversal_signals import ALL_CANDIDATES, CANDIDATES, FOCUSED_FAMILIES  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "focused_reversal_recovery"
DOCS_OUT = ROOT / "docs" / "research" / "focused_reversal_recovery"
PLAN_PATH = DOCS_OUT / "focused_reversal_recovery_research_plan.md"
REPORT_PATH = DOCS_OUT / "focused_reversal_recovery_report.md"
BROAD_OUT = ROOT / "data" / "research" / "recovery_prediction"

BROAD_FILES = [
    BROAD_OUT / "recovery_feature_panel.csv",
    BROAD_OUT / "recovery_targets.csv",
    BROAD_OUT / "recovery_ic_by_feature.csv",
    BROAD_OUT / "recovery_family_scores.csv",
    BROAD_OUT / "recovery_combination_backtests.csv",
    BROAD_OUT / "recovery_classifier_metrics.csv",
    BROAD_OUT / "baseline_vs_recovery_tilt_equity.csv",
    BROAD_OUT / "options_readiness_diagnostics.csv",
    BROAD_OUT / "recovery_run_snapshot.json",
]


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    broad_hashes_before = _hash_files(BROAD_FILES)

    print("[focused-reversal] building lagged feature panel...")
    features = fe.build_feature_panel(lag_weeks=1)
    targets = target_mod.build_targets(features)
    features.to_csv(DATA_OUT / "reversal_feature_panel.csv", index=False)
    targets.to_csv(DATA_OUT / "reversal_targets.csv", index=False)

    print("[focused-reversal] running IC and filter diagnostics...")
    ic_by_feature = ic_analysis.compute_ic_by_feature(features, targets)
    signal_scores = ic_analysis.compute_signal_scores(features, targets)
    filter_diagnostics = ic_analysis.compute_filter_diagnostics(features, targets)
    ic_by_feature.to_csv(DATA_OUT / "reversal_ic_by_feature.csv", index=False)
    signal_scores.to_csv(DATA_OUT / "reversal_signal_scores.csv", index=False)
    filter_diagnostics.to_csv(DATA_OUT / "reversal_filter_diagnostics.csv", index=False)

    print("[focused-reversal] training simple focused classifiers...")
    classifier_metrics, classifier_predictions = classifier.run_classifiers(features, targets)
    classifier_metrics.to_csv(DATA_OUT / "reversal_classifier_metrics.csv", index=False)

    print("[focused-reversal] running ETF tilt backtests...")
    backtests, equity, _ = backtest.run_backtests(features, targets, classifier_predictions)
    backtests.to_csv(DATA_OUT / "reversal_backtests.csv", index=False)
    equity.to_csv(DATA_OUT / "baseline_vs_reversal_tilt_equity.csv")

    print("[focused-reversal] running placebo tests...")
    placebo_tests = placebo.run_placebo_tests(features, targets, reference_candidate="focused_reversal_composite", n_iter=200)
    placebo_tests.to_csv(DATA_OUT / "reversal_placebo_tests.csv", index=False)

    print("[focused-reversal] running options-readiness diagnostic...")
    options_readiness = validation.build_options_readiness(features, targets, classifier_predictions)
    options_readiness.to_csv(DATA_OUT / "options_readiness_diagnostics.csv", index=False)

    gates, verdict = validation.evaluate_gates(
        signal_scores,
        ic_by_feature,
        backtests,
        classifier_metrics,
        filter_diagnostics,
        placebo_tests,
        options_readiness,
    )

    _write_plan()
    _write_report(
        signal_scores,
        filter_diagnostics,
        backtests,
        classifier_metrics,
        placebo_tests,
        options_readiness,
        gates,
        verdict,
    )

    broad_hashes_after = _hash_files(BROAD_FILES)
    snapshot = {
        "experiment": "focused_reversal_recovery_research",
        "standalone_research": True,
        "not_a_track": True,
        "verdict": verdict,
        "feature_lag_weeks": 1,
        "target_tickers": fe.TARGET_TICKERS,
        "focused_families": list(FOCUSED_FAMILIES.keys()),
        "candidates": ALL_CANDIDATES,
        "tilt_sizes": backtest.TILT_SIZES,
        "default_tilt_size": backtest.DEFAULT_TILT,
        "credit_and_volatility_role": "filters_only_not_primary_alpha",
        "previous_recovery_prediction_hashes_before": broad_hashes_before,
        "previous_recovery_prediction_hashes_after": broad_hashes_after,
        "previous_recovery_prediction_outputs_preserved": broad_hashes_before == broad_hashes_after,
        "gates": gates.to_dict(orient="records"),
        "best_default_candidate": _best_default_candidate(backtests),
        "proxy_note": "ETF re-risking research first; options-readiness is diagnostic only, no option-chain strategy tested.",
    }
    (DATA_OUT / "reversal_run_snapshot.json").write_text(json.dumps(snapshot, indent=2, default=str) + "\n")

    print(f"[focused-reversal] verdict: {verdict}")
    print(f"[focused-reversal] outputs -> {DATA_OUT}")
    print(f"[focused-reversal] report  -> {REPORT_PATH}")


def _write_plan() -> None:
    lines = [
        "# Focused Reversal Recovery Research Plan",
        "",
        "> Standalone research experiment. This is not Track A/B/C/D. It does not",
        "> modify production allocation logic and does not promote anything into production.",
        "",
        "## Research Question",
        "",
        "After recent weakness or drawdown in SPY/QQQ, can simple reversal signals",
        "identify bounce setups that improve the ETF baseline and beat random timing?",
        "",
        "## Focused Signal Families",
        "",
        "1. Short-horizon reversal.",
        "2. Drawdown reversal.",
        "3. Momentum/reversal interaction.",
        "",
        "Breadth thrust, credit improvement, and volatility normalization are not",
        "primary alpha families in this experiment. Credit and volatility are used",
        "only as coarse filters to avoid panic, deteriorating credit, and exploding volatility.",
        "",
        "## Predeclared Candidates",
        "",
    ]
    for candidate, meta in CANDIDATES.items():
        lines.append(f"- `{candidate}`: {meta['description']}.")
    lines += [
        "- `classifier_logistic_reversal`: simple train-only logistic classifier on focused reversal features.",
        "- `classifier_ridge_reversal`: simple train-only ridge probability model on focused reversal features.",
        "",
        "## Portfolio Test",
        "",
        "The baseline ETF strategy is left unchanged. When a signal fires, the research",
        "overlay tests +2.5%, +5.0%, and +7.5% SPY/QQQ tilts, funded against the",
        "existing baseline return stream with no leverage. The predeclared default is +5.0%.",
        "",
        "## Validation",
        "",
        "The run reports train/holdout IC, filter false-positive diagnostics, backtest",
        "metrics, random-entry placebo with the same signal frequency, best/top-3",
        "signal-period removal, subperiod checks, classifier precision, and a conservative",
        "options-readiness diagnostic. Final verdicts may be REJECT or RESEARCH-ONLY.",
        "",
        "## Causality",
        "",
        "Features are built from weekly data and shifted one week before any signal score",
        "or classifier input is used. Forward targets are stored in a separate file.",
    ]
    PLAN_PATH.write_text("\n".join(lines) + "\n")


def _write_report(
    signal_scores: pd.DataFrame,
    filter_diagnostics: pd.DataFrame,
    backtests: pd.DataFrame,
    classifier_metrics: pd.DataFrame,
    placebo_tests: pd.DataFrame,
    options_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    verdict: str,
) -> None:
    baseline = backtests[backtests["candidate"] == "baseline"].iloc[0]
    best = _best_default_row(backtests)
    focused = _default_row(backtests, "focused_reversal_composite")
    placebo_row = _default_row(backtests, "random_timing_placebo")
    broad_ref = backtests[backtests["candidate"] == "broad_previous_best_reference"]
    broad_sharpe = float(broad_ref["overlay_sharpe"].iloc[0]) if len(broad_ref) and "overlay_sharpe" in broad_ref else np.nan
    best_family = _best_train_family(signal_scores)
    best_readiness = options_readiness.sort_values("avg_8w_move_surplus_vs_rough_breakeven", ascending=False).head(1)
    best_ready_name = best_readiness.iloc[0]["candidate"] if len(best_readiness) else "n/a"
    filter_help = _filter_help_summary(filter_diagnostics)

    lines = [
        "# Focused Reversal Recovery Research Report",
        "",
        "> Standalone research experiment. Not production. No allocation logic was modified.",
        "",
        f"**Final verdict: `{verdict}`**",
        "",
        "## Summary",
        "",
        f"Best default +5% candidate by Sharpe: `{best.get('candidate', 'n/a')}`.",
        f"Best focused train IC family: `{best_family}`.",
        f"Best default candidate Sharpe: {_fmt(best.get('overlay_sharpe'))} vs baseline {_fmt(baseline.get('overlay_sharpe'))}.",
        f"Best default incremental Sharpe: {_fmt(best.get('incremental_sharpe'))}; incremental CAGR: {_fmt(best.get('incremental_cagr'), pct=True)}.",
        f"Focused composite Sharpe: {_fmt(focused.get('overlay_sharpe'))}; random timing placebo Sharpe: {_fmt(placebo_row.get('overlay_sharpe'))}; prior broad reference Sharpe: {_fmt(broad_sharpe)}.",
        f"Options-readiness best candidate: `{best_ready_name}`.",
        "",
        "## Signal Scores",
        "",
        "| Family/Candidate | Window | Rank IC | Precision Top Quintile | Failed Bounce | Crash Continuation | Avg Fwd 8w Top Quintile |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    score_rows = signal_scores[signal_scores["target"] == "fwd_8w_return"].copy()
    for _, r in score_rows.iterrows():
        name = r["candidate"] if isinstance(r.get("candidate"), str) and r.get("candidate") else r["family"]
        lines.append(
            f"| `{name}` | {r['window']} | {_fmt(r['rank_ic'])} | "
            f"{_fmt(r['strong_bounce_precision_top_quintile'], pct=True)} | "
            f"{_fmt(r['failed_bounce_rate_top_quintile'], pct=True)} | "
            f"{_fmt(r['crash_continuation_rate_top_quintile'], pct=True)} | "
            f"{_fmt(r['avg_forward_return_top_quintile'], pct=True)} |"
        )

    lines += [
        "",
        "## Filter Diagnostics",
        "",
        f"{filter_help}",
        "",
        "| Candidate | Window | Raw Rows | Filtered Rows | Precision Delta | Failed Delta | Crash Delta |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in filter_diagnostics.iterrows():
        if r["window"] != "full":
            continue
        lines.append(
            f"| `{r['candidate']}` | {r['window']} | {int(r['raw_signal_rows'])} | {int(r['filtered_signal_rows'])} | "
            f"{_fmt(r['precision_delta'], pct=True)} | {_fmt(r['failed_bounce_delta'], pct=True)} | "
            f"{_fmt(r['crash_continuation_delta'], pct=True)} |"
        )

    lines += [
        "",
        "## ETF Tilt Backtests",
        "",
        "| Candidate | Tilt | Sharpe | CAGR | MaxDD | CVaR 5% | Inc Sharpe | Inc CAGR | Ex Top 3 Sharpe | Holdout Sharpe |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in backtests.iterrows():
        if r.get("comparison_kind") == "broad_reference_only" or r.get("is_default_tilt") is True or str(r.get("is_default_tilt")).lower() == "true":
            lines.append(
                f"| `{r['candidate']}` | {_fmt(r['tilt_size'], pct=True)} | {_fmt(r.get('overlay_sharpe'))} | "
                f"{_fmt(r.get('overlay_cagr'), pct=True)} | {_fmt(r.get('overlay_max_drawdown'), pct=True)} | "
                f"{_fmt(r.get('overlay_cvar_5'), pct=True)} | {_fmt(r.get('incremental_sharpe'))} | "
                f"{_fmt(r.get('incremental_cagr'), pct=True)} | {_fmt(r.get('sharpe_ex_top3_signal_periods'))} | "
                f"{_fmt(r.get('holdout_sharpe'))} |"
            )

    lines += [
        "",
        "## Classifiers",
        "",
        "| Model | Window | Precision | Base Rate | FPR | Risk-Off FPR | Failed Bounce |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model in ["classifier_logistic_reversal", "classifier_ridge_reversal"]:
        for window in ["train", "holdout"]:
            lines.append(
                f"| `{model}` | {window} | {_fmt(_metric(classifier_metrics, model, window, 'precision_top_quartile'), pct=True)} | "
                f"{_fmt(_metric(classifier_metrics, model, window, 'base_rate'), pct=True)} | "
                f"{_fmt(_metric(classifier_metrics, model, window, 'false_positive_rate'), pct=True)} | "
                f"{_fmt(_metric(classifier_metrics, model, window, 'risk_off_false_positive_rate'), pct=True)} | "
                f"{_fmt(_metric(classifier_metrics, model, window, 'failed_bounce_rate_top_quartile'), pct=True)} |"
            )

    lines += [
        "",
        "## Placebo Tests",
        "",
        "| Test | Reference Sharpe | Placebo Mean Sharpe | Placebo P95 Sharpe | Placebo Beat Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in placebo_tests.iterrows():
        lines.append(
            f"| `{r['test']}` | {_fmt(r['reference_sharpe'])} | {_fmt(r['placebo_mean_sharpe'])} | "
            f"{_fmt(r['placebo_p95_sharpe'])} | {_fmt(r['pct_placebo_beating_reference'], pct=True)} |"
        )

    lines += [
        "",
        "## Options-Readiness Diagnostic",
        "",
        "No options strategy is implemented. This only checks whether the ETF signal",
        "identifies forward moves large enough to justify future option-chain research.",
        "",
        "| Candidate | Signals/Yr | Avg Fwd 8w | Ex Top 3 Avg 8w | Breakeven | Surplus | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in options_readiness.iterrows():
        lines.append(
            f"| `{r['candidate']}` | {_fmt(r['signals_per_year'])} | {_fmt(r['avg_fwd_8w_return'], pct=True)} | "
            f"{_fmt(r['avg_fwd_8w_return_ex_top3'], pct=True)} | {_fmt(r['rough_option_breakeven_move'], pct=True)} | "
            f"{_fmt(r['avg_8w_move_surplus_vs_rough_breakeven'], pct=True)} | {r['options_readiness']} |"
        )

    lines += [
        "",
        "## Validation Gates",
        "",
        "| # | Gate | Result | Detail |",
        "|---:|---|---|---|",
    ]
    for _, r in gates.iterrows():
        lines.append(f"| {int(r['gate_number'])} | `{r['gate']}` | {'PASS' if r['pass'] else 'FAIL'} | {r['detail']} |")

    lines += [
        "",
        "## Required Answers",
        "",
        f"1. Did focused reversal research improve over broad recovery prediction? Focused composite Sharpe was {_fmt(focused.get('overlay_sharpe'))} vs prior broad reference {_fmt(broad_sharpe)}; the IC comparison is gate 2.",
        f"2. Which reversal candidate worked best? `{best.get('candidate', 'n/a')}` by default +5% Sharpe.",
        f"3. Did short-horizon reversal remain the best family? Best focused train IC family was `{best_family}`.",
        "4. Did drawdown reversal help? Its train/holdout rank IC and backtest row are reported above; it is not assumed helpful unless it clears those rows.",
        "5. Did momentum/reversal interaction help? Its standalone score and candidate rows are reported separately from the composite.",
        f"6. Did credit/vol filters reduce false positives? {filter_help}",
        f"7. Did any candidate beat random timing placebo? Best default candidate Sharpe {_fmt(best.get('overlay_sharpe'))} vs placebo {_fmt(placebo_row.get('overlay_sharpe'))}.",
        f"8. Did any candidate improve ETF baseline Sharpe by +0.05? Best incremental Sharpe was {_fmt(best.get('incremental_sharpe'))}.",
        f"9. Did any candidate improve CAGR by +0.25%? Best incremental CAGR was {_fmt(best.get('incremental_cagr'), pct=True)}.",
        f"10. Did max drawdown and CVaR remain acceptable? Best default MaxDD {_fmt(best.get('overlay_max_drawdown'), pct=True)} vs baseline {_fmt(best.get('baseline_max_drawdown'), pct=True)}; CVaR 5% {_fmt(best.get('overlay_cvar_5'), pct=True)} vs baseline {_fmt(best.get('baseline_cvar_5'), pct=True)}.",
        f"11. Did results survive best/top-3 removal? Best ex-best Sharpe {_fmt(best.get('sharpe_ex_best_signal_period'))}; ex-top3 {_fmt(best.get('sharpe_ex_top3_signal_periods'))}.",
        f"12. Did holdout performance remain positive? Best holdout Sharpe was {_fmt(best.get('holdout_sharpe'))}.",
        f"13. Was options-readiness improved? Best readiness candidate was `{best_ready_name}` with status `{best_readiness.iloc[0]['options_readiness'] if len(best_readiness) else 'n/a'}`.",
        f"14. Should this be rejected, research-only, candidate for ETF re-risking, or candidate for future options testing? `{verdict}`.",
        "15. What should be tried next? If not rejected, the next step is stricter walk-forward thresholding and cleaner funding simulation for the strongest single candidate; options should wait for real option-chain data.",
        "",
        "## Verdict Explanation",
        "",
        _verdict_explanation(verdict, gates),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def _hash_files(paths: list[Path]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        if not path.exists():
            out[rel] = None
            continue
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        out[rel] = h.hexdigest()
    return out


def _best_default_candidate(backtests: pd.DataFrame) -> dict:
    row = _best_default_row(backtests)
    return row.to_dict() if len(row) else {}


def _best_default_row(backtests: pd.DataFrame) -> pd.Series:
    sub = backtests[
        (backtests["candidate"].isin(ALL_CANDIDATES))
        & (backtests["is_default_tilt"].astype(str).str.lower().isin(["true", "1"]))
    ].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.sort_values("overlay_sharpe", ascending=False).iloc[0]


def _default_row(backtests: pd.DataFrame, candidate: str) -> pd.Series:
    sub = backtests[
        (backtests["candidate"] == candidate)
        & (backtests["is_default_tilt"].astype(str).str.lower().isin(["true", "1"]))
    ]
    return sub.iloc[0] if len(sub) else pd.Series(dtype=float)


def _best_train_family(signal_scores: pd.DataFrame) -> str:
    sub = signal_scores[
        (signal_scores["candidate"].fillna("") == "")
        & (signal_scores["window"] == "train")
        & (signal_scores["target"] == "fwd_8w_return")
    ].copy()
    if sub.empty:
        return "n/a"
    return str(sub.sort_values("rank_ic", ascending=False).iloc[0]["family"])


def _filter_help_summary(filter_diagnostics: pd.DataFrame) -> str:
    full = filter_diagnostics[filter_diagnostics["window"] == "full"]
    if full.empty:
        return "Filter diagnostics were unavailable."
    crash_delta = float(full["crash_continuation_delta"].mean())
    failed_delta = float(full["failed_bounce_delta"].mean())
    precision_delta = float(full["precision_delta"].mean())
    return (
        f"Average filter effect: precision delta {_fmt(precision_delta, pct=True)}, "
        f"failed-bounce delta {_fmt(failed_delta, pct=True)}, crash-continuation delta {_fmt(crash_delta, pct=True)}."
    )


def _metric(df: pd.DataFrame, model: str, window: str, metric: str) -> float:
    sub = df[(df["model"] == model) & (df["window"] == window) & (df["metric"] == metric)]
    return float(sub["value"].iloc[0]) if len(sub) else np.nan


def _fmt(x, pct: bool = False) -> str:
    try:
        val = float(x)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(val):
        return "n/a"
    return f"{val * 100:.2f}%" if pct else f"{val:.3f}"


def _verdict_explanation(verdict: str, gates: pd.DataFrame) -> str:
    failed = gates[~gates["pass"]]
    if verdict == "REJECT":
        return "The focused reversal setup did not clear enough signal and portfolio gates to justify further ETF or options testing."
    if verdict == "RESEARCH-ONLY":
        important = ", ".join(failed["gate"].head(5).astype(str).tolist())
        return f"The evidence has some research value, but portfolio or placebo gates remain too weak for candidacy. Key failed gates: {important}."
    if verdict == "CANDIDATE FOR ETF RE-RISKING TESTING":
        return "The ETF overlay passed most portfolio gates, but this remains research-only until stricter walk-forward and implementation testing."
    return "Forward ETF moves were large enough for future options research, but no options strategy or chain-aware result was tested here."


if __name__ == "__main__":
    main()

