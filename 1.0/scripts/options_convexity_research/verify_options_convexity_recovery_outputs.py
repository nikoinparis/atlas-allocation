"""Verify Options Convexity Recovery Research outputs.

The verifier is intentionally independent of the report narrative. It checks
that the recovery experiment stayed standalone, produced all requested files,
respected sizing constraints, used only SPY/QQQ, and did not promote a fragile
proxy result.
"""

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

from options_convexity import (  # noqa: E402
    option_data,
    recovery_backtest as rbt,
    recovery_option_structures as ros,
    recovery_signal_engine as rse,
)

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_recovery_report.md"
SNAPSHOT_PATH = DATA_OUT / "recovery_run_snapshot.json"

VALID_VERDICTS = {"REJECT", "RESEARCH-ONLY", "CANDIDATE FOR FURTHER TESTING"}

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
    "data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_frontier_phase5_fragility_guard.csv",
]

V1_V2_OUTPUTS = [
    DATA_OUT / "options_overlay_trades.csv",
    DATA_OUT / "options_overlay_metrics.csv",
    DATA_OUT / "baseline_vs_options_equity.csv",
    DATA_OUT / "options_overlay_run_snapshot.json",
    DATA_OUT / "options_v2_trades.csv",
    DATA_OUT / "options_v2_metrics.csv",
    DATA_OUT / "options_v2_baseline_vs_overlay_equity.csv",
    DATA_OUT / "options_v2_run_snapshot.json",
    DOCS_OUT / "options_convexity_research_report.md",
    DOCS_OUT / "options_convexity_v2_research_report.md",
]

RECOVERY_REQUIRED = [
    DATA_OUT / "recovery_options_trades.csv",
    DATA_OUT / "recovery_options_metrics.csv",
    DATA_OUT / "recovery_signal_diagnostics.csv",
    DATA_OUT / "recovery_structure_comparison.csv",
    DATA_OUT / "recovery_baseline_vs_overlay_equity.csv",
    DATA_OUT / "recovery_tactical_etf_comparison.csv",
    DATA_OUT / "recovery_run_snapshot.json",
    DOCS_OUT / "options_convexity_recovery_research_plan.md",
    DOCS_OUT / "options_convexity_recovery_report.md",
]


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
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as exc:  # pragma: no cover
        cr.check("production_untouched", False, f"git status failed: {exc}")
        return
    modified = set()
    for line in out.splitlines():
        status, path = line[:2], line[3:].strip()
        if status.strip() and status != "??":
            modified.add(path)
    touched = [p for p in PROTECTED_PATHS if p in modified]
    cr.check("production_untouched", not touched, "no protected production files modified" if not touched else f"MODIFIED: {touched}")


def check_v1_v2_preserved(cr: CheckResult) -> None:
    missing = [str(p.relative_to(ROOT)) for p in V1_V2_OUTPUTS if not p.exists()]
    cr.check("v1_v2_outputs_preserved", not missing, "all v1/v2 outputs present" if not missing else f"missing: {missing}")


def check_required_outputs(cr: CheckResult) -> None:
    missing = [str(p.relative_to(ROOT)) for p in RECOVERY_REQUIRED if not p.exists()]
    cr.check("recovery_required_outputs_exist", not missing, "all present" if not missing else f"missing: {missing}")


def check_trades_scope(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("trades_scope", True, "no trades; scope vacuously valid")
        return
    bad_underlyings = sorted(set(trades["underlying"].astype(str)) - set(rse.RECOVERY_UNDERLYINGS))
    bad_structures = sorted(set(trades["structure"].astype(str)) - set(rbt.STRUCTURE_BUILDERS))
    bad_dte = []
    for _, row in trades.iterrows():
        bucket = str(row["dte_bucket"])
        if bucket not in rbt.DTE_BUCKETS:
            bad_dte.append((bucket, "unknown"))
            continue
        rng = rbt.DTE_BUCKETS[bucket]
        if not (rng["min"] <= float(row["dte_days"]) <= rng["max"]):
            bad_dte.append((bucket, row["dte_days"]))
    ok = not bad_underlyings and not bad_structures and not bad_dte
    cr.check(
        "trades_scope",
        ok,
        "SPY/QQQ only; structures and DTE buckets valid"
        if ok
        else f"bad_underlyings={bad_underlyings}, bad_structures={bad_structures}, bad_dte={bad_dte[:5]}",
    )


def check_sizing_caps(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("sizing_caps", True, "no trades")
        return
    premium = pd.to_numeric(trades["premium_fraction"], errors="coerce")
    per_trade_ok = bool((premium <= rbt.PER_TRADE_RISK + 1e-9).all())

    events: list[tuple[pd.Timestamp, int, float]] = []
    for _, row in trades.iterrows():
        events.append((pd.Timestamp(row["open_date"]), 1, float(row["premium_fraction"])))
        events.append((pd.Timestamp(row["exit_date"]), 0, -float(row["premium_fraction"])))
    # Process closes before opens on the same date.
    events.sort(key=lambda e: (e[0], e[1]))
    running = concurrent_max = 0.0
    for _, _, delta in events:
        running += delta
        concurrent_max = max(concurrent_max, running)

    by_year = trades.assign(year=pd.to_datetime(trades["open_date"]).dt.year).groupby("year")["premium_fraction"].sum()
    annual_max = float(by_year.max()) if len(by_year) else 0.0

    ok = per_trade_ok and concurrent_max <= rbt.MAX_CONCURRENT_RISK + 1e-9 and annual_max <= rbt.MAX_ANNUAL_RISK + 1e-9
    cr.check(
        "sizing_caps",
        ok,
        f"per_trade_max={premium.max():.4f}, concurrent_max={concurrent_max:.4f}, annual_max={annual_max:.4f}",
    )


def check_trades_respect_recovery_rules(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("trades_respect_recovery_rules", True, "no trades")
        return
    signals = rse.build_recovery_signals()
    states = option_data.load_market_states()["market_state"].astype(str)
    weights = option_data.load_baseline_weights()
    builders = rbt.STRUCTURE_BUILDERS

    violations = []
    for _, row in trades.iterrows():
        date = pd.Timestamp(row["open_date"])
        ticker = str(row["underlying"])
        features = signals.feature_row(date, ticker)
        structure = builders[str(row["structure"])](float(row["open_spot"]), float(row["sigma"]), float(row["dte_days"]))
        ros.price_structure(structure, rbt.ENTRY_SLIPPAGE_FRAC)
        decision = rse.evaluate_recovery_entry(
            features,
            market_state=str(states.loc[date]),
            baseline_weight=_get(weights, date, ticker, 0.0),
            breakeven_move=structure.breakeven_move,
            horizon_weeks=max((float(row["dte_days"]) - rbt.EXIT_DTE) / 7.0, 1.0),
            holding_weeks=max((float(row["dte_days"]) - rbt.EXIT_DTE) / 7.0, 1.0),
            gate_flags=dict(rse.DEFAULT_GATE_FLAGS),
        )
        if not decision.active:
            violations.append((str(date.date()), ticker, decision.reasons_failed))

    cr.check(
        "trades_respect_recovery_rules",
        not violations,
        f"all {len(trades)} trades pass recovery entry gates" if not violations else f"{len(violations)} violations: {violations[:5]}",
    )


def check_valid_option_economics(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("valid_option_economics", True, "no trades")
        return
    required = ["entry_cost_basis", "max_loss_per_share", "long_strike", "sigma", "trade_return", "incremental_dollars"]
    missing = [c for c in required if c not in trades.columns]
    if missing:
        cr.check("valid_option_economics", False, f"missing columns: {missing}")
        return
    numeric = trades[required].apply(pd.to_numeric, errors="coerce")
    bad = numeric.isna().any(axis=1) | (numeric["max_loss_per_share"] <= 0) | (numeric["long_strike"] <= 0) | (numeric["sigma"] <= 0)
    cr.check("valid_option_economics", not bool(bad.any()), "all option economics finite/positive" if not bad.any() else f"{int(bad.sum())} bad rows")


def check_no_lookahead(cr: CheckResult) -> None:
    prices = option_data.load_weekly_prices(rse.RECOVERY_UNDERLYINGS)
    unlagged_12 = prices.pct_change(12)
    signals = rse.build_recovery_signals()
    lagged_12 = signals.per_ticker["ret_12w"].dropna(how="all")
    shifted = unlagged_12.shift(1).reindex(lagged_12.index)
    matches = np.isclose(lagged_12.values, shifted.values, equal_nan=True)
    cr.check(
        "no_lookahead_signals",
        bool(matches.all()),
        "ret_12w equals prior-week value" if matches.all() else "lagged ret_12w mismatch",
    )


def check_metrics_present(cr: CheckResult) -> None:
    path = DATA_OUT / "recovery_options_metrics.csv"
    if not path.exists():
        cr.check("key_metrics_present", False, "metrics file missing")
        return
    m = pd.read_csv(path)
    have = set(m["metric"].astype(str).unique())
    required = {
        "cagr",
        "ann_return",
        "ann_vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "cvar_1",
        "upside_capture",
        "downside_capture",
        "option_hit_rate",
        "avg_trade_return",
        "median_trade_return",
        "worst_trade_return",
        "best_trade_return",
        "sharpe_ex_best",
        "sharpe_ex_top3",
        "premium_at_risk_per_year",
        "activations_per_year",
        "max_concurrent_risk",
        "avg_dte",
        "avg_moneyness",
        "incremental_cagr_vs_baseline",
        "options_minus_tilt_sharpe",
    }
    missing = sorted(required - have)
    cr.check("key_metrics_present", not missing, "all key metrics present" if not missing else f"missing: {missing}")


def check_tactical_comparison(cr: CheckResult) -> None:
    path = DATA_OUT / "recovery_tactical_etf_comparison.csv"
    if not path.exists():
        cr.check("tactical_comparison_present", False, "file missing")
        return
    df = pd.read_csv(path)
    required = {"variant", "options_sharpe", "tilt_sharpe", "options_minus_tilt_sharpe", "options_cagr", "tilt_cagr"}
    missing = sorted(required - set(df.columns))
    cr.check("tactical_comparison_present", not missing and len(df) > 0, f"{len(df)} rows" if not missing else f"missing: {missing}")


def check_verdict(cr: CheckResult) -> None:
    if not REPORT_PATH.exists() or not SNAPSHOT_PATH.exists():
        cr.check("verdict_present", False, "report or snapshot missing")
        return
    report = REPORT_PATH.read_text()
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    verdict = snapshot.get("verdict")
    found = [v for v in VALID_VERDICTS if v in report]
    cr.check("verdict_present", verdict in VALID_VERDICTS and verdict in found, f"snapshot={verdict}, report={found}")

    gates = snapshot.get("gates", {})
    all_pass = all(g.get("pass") for g in gates.values()) if gates else False
    if all_pass:
        ok = verdict == "CANDIDATE FOR FURTHER TESTING"
        detail = f"all gates pass -> {verdict}"
    else:
        ok = verdict in {"RESEARCH-ONLY", "REJECT"}
        detail = f"not all gates pass -> {verdict}"
    cr.check("verdict_default_consistent", ok, detail)

    robust = gates.get("not_one_trade", {}).get("pass", False) and gates.get("survive_top3_removal", {}).get("pass", False)
    cr.check(
        "fragility_not_promoted",
        robust or verdict != "CANDIDATE FOR FURTHER TESTING",
        "fragile result not promoted" if not robust else "robustness gates pass",
    )
    cr.check(
        "proxy_warning_documented",
        "PROXY RESULTS" in report and "not production" in report.lower(),
        "proxy/non-production caveats present",
    )


def _get(df: pd.DataFrame, date, ticker: str, default=np.nan) -> float:
    try:
        val = df.loc[date, ticker]
    except (KeyError, IndexError):
        return default
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if np.isfinite(val) else default


def main() -> int:
    print("[verify recovery] Options Convexity Recovery outputs\n")
    cr = CheckResult()
    trades_path = DATA_OUT / "recovery_options_trades.csv"
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    check_production_untouched(cr)
    check_v1_v2_preserved(cr)
    check_required_outputs(cr)
    check_trades_scope(cr, trades)
    check_sizing_caps(cr, trades)
    check_trades_respect_recovery_rules(cr, trades)
    check_valid_option_economics(cr, trades)
    check_no_lookahead(cr)
    check_metrics_present(cr)
    check_tactical_comparison(cr)
    check_verdict(cr)

    print(f"\n[verify recovery] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify recovery] FAILURES:")
        for failure in cr.failed:
            print(f"  - {failure}")
        return 1
    print("[verify recovery] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
