"""Verify standalone Recovery Prediction Research outputs."""

from __future__ import annotations

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

from recovery_prediction.feature_engineering import TARGET_TICKERS, load_weekly_prices  # noqa: E402
from recovery_prediction.signal_families import FAMILIES, FAMILY_SCORE_COLUMNS  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "recovery_prediction"
DOCS_OUT = ROOT / "docs" / "research" / "recovery_prediction"

REQUIRED = [
    DATA_OUT / "recovery_feature_panel.csv",
    DATA_OUT / "recovery_targets.csv",
    DATA_OUT / "recovery_ic_by_feature.csv",
    DATA_OUT / "recovery_ic_by_regime.csv",
    DATA_OUT / "recovery_family_scores.csv",
    DATA_OUT / "recovery_family_backtests.csv",
    DATA_OUT / "recovery_combination_backtests.csv",
    DATA_OUT / "recovery_classifier_metrics.csv",
    DATA_OUT / "recovery_ensemble_predictions.csv",
    DATA_OUT / "baseline_vs_recovery_tilt_equity.csv",
    DATA_OUT / "options_readiness_diagnostics.csv",
    DATA_OUT / "recovery_run_snapshot.json",
    DOCS_OUT / "recovery_prediction_research_plan.md",
    DOCS_OUT / "recovery_prediction_research_report.md",
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

VALID_VERDICTS = {
    "REJECT",
    "RESEARCH-ONLY",
    "CANDIDATE FOR ETF RE-RISKING TESTING",
    "CANDIDATE FOR FUTURE OPTIONS TESTING",
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


def check_production_untouched(cr: CheckResult) -> None:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    modified = set()
    for line in out.splitlines():
        status, path = line[:2], line[3:].strip()
        if status.strip() and status != "??":
            modified.add(path)
    touched = [p for p in PROTECTED_PATHS if p in modified]
    cr.check("production_untouched", not touched, "no protected production files modified" if not touched else f"MODIFIED: {touched}")


def check_required_outputs(cr: CheckResult) -> None:
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
    cr.check("required_outputs_exist", not missing, "all present" if not missing else f"missing: {missing}")


def check_feature_target_separation(cr: CheckResult, features: pd.DataFrame, targets: pd.DataFrame) -> None:
    target_like = [c for c in features.columns if c.startswith("fwd_") or c.endswith("_label")]
    required_target_cols = {"fwd_4w_return", "fwd_8w_return", "fwd_12w_return", "strong_recovery_label", "fake_bounce_label", "rerisk_label"}
    cr.check(
        "feature_target_separation",
        not target_like and required_target_cols.issubset(set(targets.columns)),
        "features exclude targets; target file has forward labels"
        if not target_like and required_target_cols.issubset(set(targets.columns))
        else f"target_like_in_features={target_like}, missing_targets={sorted(required_target_cols - set(targets.columns))}",
    )


def check_feature_lag(cr: CheckResult, features: pd.DataFrame) -> None:
    prices = load_weekly_prices()[TARGET_TICKERS]
    ok = True
    details = []
    for ticker in TARGET_TICKERS:
        expected = prices[ticker].pct_change(4).shift(1)
        sub = features[features["ticker"] == ticker].copy()
        sub["Date"] = pd.to_datetime(sub["Date"])
        got = pd.to_numeric(sub.set_index("Date")["ret_4w"], errors="coerce").reindex(expected.index)
        mask = got.notna() & expected.notna()
        matches = np.isclose(got[mask].values, expected[mask].values, equal_nan=True)
        if not matches.all():
            ok = False
            details.append(ticker)
    lag_col_ok = "feature_lag_weeks" in features.columns and set(pd.to_numeric(features["feature_lag_weeks"], errors="coerce").dropna().unique()) == {1}
    cr.check("feature_panel_lagged", ok and lag_col_ok, "ret_4w equals prior-week value for SPY/QQQ" if ok and lag_col_ok else f"lag mismatch={details}, lag_col_ok={lag_col_ok}")


def check_families(cr: CheckResult, features: pd.DataFrame, ic: pd.DataFrame, family_bt: pd.DataFrame) -> None:
    have_scores = set(FAMILY_SCORE_COLUMNS).issubset(set(features.columns))
    have_ic = set(FAMILIES.keys()).issubset(set(ic["family"].astype(str)))
    have_bt = all(any(f in str(v) for v in family_bt["variant"]) for f in FAMILIES)
    cr.check("six_signal_families_present", have_scores and have_ic and have_bt, f"scores={have_scores}, ic={have_ic}, backtests={have_bt}")


def check_backtests_and_metrics(cr: CheckResult, combo: pd.DataFrame, classifier: pd.DataFrame, equity: pd.DataFrame, readiness: pd.DataFrame) -> None:
    combo_required = {
        "equal_weight_six_family_composite",
        "regime_gated_composite",
        "and_gated_drawdown_credit_vol",
        "or_score_composite",
        "momentum_reversal_interaction",
        "classifier_logistic_l2",
        "classifier_ridge_probability",
        "random_timing_placebo",
    }
    have_combo = combo_required.issubset(set(combo["variant"].astype(str)))
    required_metrics = {"overlay_sharpe", "overlay_max_drawdown", "overlay_cvar_5", "overlay_cagr"}
    have_metrics = required_metrics.issubset(set(combo.columns))
    have_classifier = {"logistic_l2", "ridge_probability"}.issubset(set(classifier["model"].astype(str)))
    have_equity = "baseline_equity" in equity.columns and any("regime_gated_composite_equity" in c for c in equity.columns)
    have_readiness = len(readiness) > 0 and "avg_8w_move_surplus_vs_rough_breakeven" in readiness.columns
    cr.check(
        "backtests_metrics_placebo_readiness",
        have_combo and have_metrics and have_classifier and have_equity and have_readiness,
        f"combo={have_combo}, metrics={have_metrics}, classifier={have_classifier}, equity={have_equity}, readiness={have_readiness}",
    )


def check_verdict(cr: CheckResult) -> None:
    report = (DOCS_OUT / "recovery_prediction_research_report.md").read_text()
    snapshot = json.loads((DATA_OUT / "recovery_run_snapshot.json").read_text())
    verdict = snapshot.get("verdict")
    found = [v for v in VALID_VERDICTS if v in report]
    cr.check("report_has_valid_verdict", verdict in VALID_VERDICTS and verdict in found, f"snapshot={verdict}, report={found}")


def main() -> int:
    print("[verify recovery-prediction] outputs\n")
    cr = CheckResult()
    check_production_untouched(cr)
    check_required_outputs(cr)

    features = pd.read_csv(DATA_OUT / "recovery_feature_panel.csv")
    targets = pd.read_csv(DATA_OUT / "recovery_targets.csv")
    ic = pd.read_csv(DATA_OUT / "recovery_ic_by_feature.csv")
    family_bt = pd.read_csv(DATA_OUT / "recovery_family_backtests.csv")
    combo = pd.read_csv(DATA_OUT / "recovery_combination_backtests.csv")
    classifier = pd.read_csv(DATA_OUT / "recovery_classifier_metrics.csv")
    equity = pd.read_csv(DATA_OUT / "baseline_vs_recovery_tilt_equity.csv")
    readiness = pd.read_csv(DATA_OUT / "options_readiness_diagnostics.csv")

    check_feature_target_separation(cr, features, targets)
    check_feature_lag(cr, features)
    check_families(cr, features, ic, family_bt)
    check_backtests_and_metrics(cr, combo, classifier, equity, readiness)
    check_verdict(cr)

    print(f"\n[verify recovery-prediction] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify recovery-prediction] FAILURES:")
        for failure in cr.failed:
            print(f"  - {failure}")
        return 1
    print("[verify recovery-prediction] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
