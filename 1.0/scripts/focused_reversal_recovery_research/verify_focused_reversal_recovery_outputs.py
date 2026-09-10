"""Verify Focused Reversal Recovery Research outputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from focused_reversal_recovery.feature_engineering import TARGET_TICKERS, load_weekly_prices  # noqa: E402
from focused_reversal_recovery.reversal_signals import ALL_CANDIDATES, CANDIDATES, FOCUSED_FAMILIES  # noqa: E402
from focused_reversal_recovery.validation import VALID_VERDICTS  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "focused_reversal_recovery"
DOCS_OUT = ROOT / "docs" / "research" / "focused_reversal_recovery"
BROAD_OUT = ROOT / "data" / "research" / "recovery_prediction"

REQUIRED = [
    DATA_OUT / "reversal_feature_panel.csv",
    DATA_OUT / "reversal_targets.csv",
    DATA_OUT / "reversal_ic_by_feature.csv",
    DATA_OUT / "reversal_signal_scores.csv",
    DATA_OUT / "reversal_filter_diagnostics.csv",
    DATA_OUT / "reversal_backtests.csv",
    DATA_OUT / "reversal_classifier_metrics.csv",
    DATA_OUT / "reversal_placebo_tests.csv",
    DATA_OUT / "baseline_vs_reversal_tilt_equity.csv",
    DATA_OUT / "options_readiness_diagnostics.csv",
    DATA_OUT / "reversal_run_snapshot.json",
    DOCS_OUT / "focused_reversal_recovery_research_plan.md",
    DOCS_OUT / "focused_reversal_recovery_report.md",
]

PROTECTED_PATHS = [
    "scripts/production_config.py",
    "scripts/production_metrics.py",
    "scripts/production_costs.py",
    "scripts/production_allocator.py",
    "scripts/reproduce_production_candidate.py",
    "data/04_layer2b_risk_regime_engine/market_state_history.csv",
    "data/01_data_hub/weekly_prices.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv",
]

TARGET_COLS = {
    "fwd_4w_return",
    "fwd_8w_return",
    "fwd_12w_return",
    "strong_bounce_label",
    "failed_bounce_label",
    "crash_continuation_label",
    "reversal_success_label",
}


class CheckResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        line = f"{name}: {detail}".strip()
        (self.passed if ok else self.failed).append(line)
        print(f"  [{'PASS' if ok else 'FAIL'}] {line}")

    @property
    def all_ok(self) -> bool:
        return not self.failed


def main() -> int:
    print("[verify focused-reversal] outputs\n")
    cr = CheckResult()
    check_production_untouched(cr)
    check_required_outputs(cr)
    if not all(p.exists() for p in REQUIRED):
        return _finish(cr)

    features = pd.read_csv(DATA_OUT / "reversal_feature_panel.csv")
    targets = pd.read_csv(DATA_OUT / "reversal_targets.csv")
    ic = pd.read_csv(DATA_OUT / "reversal_ic_by_feature.csv")
    signal_scores = pd.read_csv(DATA_OUT / "reversal_signal_scores.csv")
    filters = pd.read_csv(DATA_OUT / "reversal_filter_diagnostics.csv")
    backtests = pd.read_csv(DATA_OUT / "reversal_backtests.csv")
    classifier = pd.read_csv(DATA_OUT / "reversal_classifier_metrics.csv")
    placebo = pd.read_csv(DATA_OUT / "reversal_placebo_tests.csv")
    equity = pd.read_csv(DATA_OUT / "baseline_vs_reversal_tilt_equity.csv")
    readiness = pd.read_csv(DATA_OUT / "options_readiness_diagnostics.csv")
    snapshot = json.loads((DATA_OUT / "reversal_run_snapshot.json").read_text())

    check_previous_recovery_outputs(cr, snapshot)
    check_feature_target_separation(cr, features, targets)
    check_feature_lag_and_targets(cr, features, targets)
    check_focused_signal_groups(cr, features, signal_scores)
    check_credit_vol_filters_only(cr, features, signal_scores)
    check_ic_backtests_metrics(cr, ic, signal_scores, backtests, classifier, placebo, equity, readiness)
    check_report_verdict(cr, snapshot)
    return _finish(cr)


def check_production_untouched(cr: CheckResult) -> None:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    modified = set()
    for line in out.splitlines():
        status = line[:2]
        path = line[3:].strip()
        if status.strip() and status != "??":
            modified.add(path)
    touched = [p for p in PROTECTED_PATHS if p in modified]
    cr.check("production_untouched", not touched, "no protected production files modified" if not touched else f"MODIFIED: {touched}")


def check_required_outputs(cr: CheckResult) -> None:
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
    cr.check("required_outputs_exist", not missing, "all present" if not missing else f"missing: {missing}")


def check_previous_recovery_outputs(cr: CheckResult, snapshot: dict) -> None:
    before = snapshot.get("previous_recovery_prediction_hashes_before", {})
    after = snapshot.get("previous_recovery_prediction_hashes_after", {})
    current = _hash_paths([ROOT / p for p in after])
    preserved = snapshot.get("previous_recovery_prediction_outputs_preserved") is True
    cr.check(
        "previous_recovery_prediction_outputs_preserved",
        preserved and before == after and after == current,
        "broad recovery output hashes unchanged"
        if preserved and before == after and after == current
        else "broad recovery output hash mismatch",
    )


def check_feature_target_separation(cr: CheckResult, features: pd.DataFrame, targets: pd.DataFrame) -> None:
    target_like = [
        c
        for c in features.columns
        if c.startswith("fwd_") or c.endswith("_label") or c in {"future_8w_min_return", "future_12w_min_return"}
    ]
    missing_targets = sorted(TARGET_COLS - set(targets.columns))
    cr.check(
        "feature_target_separation",
        not target_like and not missing_targets,
        "features exclude forward targets; target file has labels"
        if not target_like and not missing_targets
        else f"target_like_in_features={target_like}, missing_targets={missing_targets}",
    )


def check_feature_lag_and_targets(cr: CheckResult, features: pd.DataFrame, targets: pd.DataFrame) -> None:
    prices = load_weekly_prices()[TARGET_TICKERS]
    ok = True
    details = []
    for ticker in TARGET_TICKERS:
        expected_feature = prices[ticker].pct_change(4).shift(1)
        sub = features[features["ticker"] == ticker].copy()
        sub["Date"] = pd.to_datetime(sub["Date"])
        got_feature = pd.to_numeric(sub.set_index("Date")["ret_4w"], errors="coerce").reindex(expected_feature.index)
        mask = got_feature.notna() & expected_feature.notna()
        if not np.isclose(got_feature[mask].values, expected_feature[mask].values, equal_nan=True).all():
            ok = False
            details.append(f"{ticker} ret_4w lag mismatch")

        expected_target = prices[ticker].shift(-8) / prices[ticker] - 1.0
        tsub = targets[targets["ticker"] == ticker].copy()
        tsub["Date"] = pd.to_datetime(tsub["Date"])
        got_target = pd.to_numeric(tsub.set_index("Date")["fwd_8w_return"], errors="coerce").reindex(expected_target.index)
        tmask = got_target.notna() & expected_target.notna()
        if not np.isclose(got_target[tmask].values, expected_target[tmask].values, equal_nan=True).all():
            ok = False
            details.append(f"{ticker} fwd_8w target mismatch")

    lag_col_ok = "feature_lag_weeks" in features.columns and set(pd.to_numeric(features["feature_lag_weeks"], errors="coerce").dropna().unique()) == {1}
    cr.check("lagged_features_and_forward_targets", ok and lag_col_ok, "ret_4w is prior-week feature; fwd_8w is future target" if ok and lag_col_ok else f"{details}, lag_col_ok={lag_col_ok}")


def check_focused_signal_groups(cr: CheckResult, features: pd.DataFrame, signal_scores: pd.DataFrame) -> None:
    focused_scores = {meta["score"] for meta in FOCUSED_FAMILIES.values()}
    active_cols = {meta["active"] for meta in CANDIDATES.values()}
    have_scores = focused_scores.issubset(set(features.columns))
    have_active = active_cols.issubset(set(features.columns))
    have_families = set(FOCUSED_FAMILIES).issubset(set(signal_scores["family"].astype(str)))
    cr.check(
        "focused_signal_groups_present",
        have_scores and have_active and have_families,
        f"scores={have_scores}, active={have_active}, families={have_families}",
    )


def check_credit_vol_filters_only(cr: CheckResult, features: pd.DataFrame, signal_scores: pd.DataFrame) -> None:
    forbidden_score_cols = [
        c
        for c in features.columns
        if c.startswith("score_credit") or c.startswith("score_vol") or c.startswith("score_breadth")
    ]
    forbidden_families = set(signal_scores["family"].astype(str)).intersection(
        {"credit_improvement", "volatility_normalization", "breadth_thrust"}
    )
    filter_cols = {"filter_credit_not_deteriorating", "filter_vol_stabilizing", "filter_reversal_entry_ok"}
    cr.check(
        "credit_vol_filters_only",
        not forbidden_score_cols and not forbidden_families and filter_cols.issubset(set(features.columns)),
        "credit/vol present as filters and absent as primary score families"
        if not forbidden_score_cols and not forbidden_families and filter_cols.issubset(set(features.columns))
        else f"forbidden_scores={forbidden_score_cols}, forbidden_families={sorted(forbidden_families)}",
    )


def check_ic_backtests_metrics(
    cr: CheckResult,
    ic: pd.DataFrame,
    signal_scores: pd.DataFrame,
    backtests: pd.DataFrame,
    classifier: pd.DataFrame,
    placebo: pd.DataFrame,
    equity: pd.DataFrame,
    readiness: pd.DataFrame,
) -> None:
    have_ic = not ic.empty and {"rank_ic", "target", "window"}.issubset(set(ic.columns))
    candidate_set = set(backtests["candidate"].astype(str))
    have_candidates = set(ALL_CANDIDATES).issubset(candidate_set)
    tilt_ok = True
    for candidate in ALL_CANDIDATES:
        sub = backtests[backtests["candidate"] == candidate]
        tilts = set(np.round(pd.to_numeric(sub["tilt_size"], errors="coerce").dropna(), 3))
        if not {0.025, 0.05, 0.075}.issubset(tilts):
            tilt_ok = False
    required_metrics = {"overlay_sharpe", "overlay_cagr", "overlay_max_drawdown", "overlay_cvar_5", "overlay_cvar_1"}
    have_metrics = required_metrics.issubset(set(backtests.columns))
    have_classifiers = {"classifier_logistic_reversal", "classifier_ridge_reversal"}.issubset(set(classifier["model"].astype(str)))
    have_placebo = not placebo.empty and {"random_entry_same_frequency", "block_bootstrap_weekly_returns"}.issubset(set(placebo["test"].astype(str)))
    have_equity = "baseline_equity" in equity.columns and any("focused_reversal_composite" in c and c.endswith("_equity") for c in equity.columns)
    have_readiness = set(ALL_CANDIDATES).issubset(set(readiness["candidate"].astype(str))) and "avg_8w_move_surplus_vs_rough_breakeven" in readiness.columns
    have_signal_scores = set(CANDIDATES).issubset(set(signal_scores["candidate"].dropna().astype(str)))
    cr.check(
        "ic_backtests_classifiers_placebo_readiness",
        have_ic and have_signal_scores and have_candidates and tilt_ok and have_metrics and have_classifiers and have_placebo and have_equity and have_readiness,
        (
            f"ic={have_ic}, signal_scores={have_signal_scores}, candidates={have_candidates}, tilt_sizes={tilt_ok}, "
            f"metrics={have_metrics}, classifiers={have_classifiers}, placebo={have_placebo}, equity={have_equity}, readiness={have_readiness}"
        ),
    )


def check_report_verdict(cr: CheckResult, snapshot: dict) -> None:
    report = (DOCS_OUT / "focused_reversal_recovery_report.md").read_text()
    verdict = snapshot.get("verdict")
    answers_ok = all(f"{i}." in report for i in range(1, 16))
    found = [v for v in VALID_VERDICTS if v in report]
    cr.check(
        "report_has_valid_verdict_and_answers",
        verdict in VALID_VERDICTS and verdict in found and "Verdict Explanation" in report and answers_ok,
        f"snapshot={verdict}, report_verdicts={found}, answers_ok={answers_ok}",
    )


def _hash_paths(paths: list[Path]) -> dict[str, str | None]:
    out = {}
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


def _finish(cr: CheckResult) -> int:
    print(f"\n[verify focused-reversal] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify focused-reversal] FAILURES:")
        for failure in cr.failed:
            print(f"  - {failure}")
        return 1
    print("[verify focused-reversal] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

