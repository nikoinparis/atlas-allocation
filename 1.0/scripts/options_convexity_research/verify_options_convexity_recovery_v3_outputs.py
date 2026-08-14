"""Verify Recovery Options Overlay v3 outputs."""

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
    recovery_v3_backtest as bt,
    recovery_v3_signal_engine as sig,
)

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_recovery_v3_report.md"
SNAPSHOT_PATH = DATA_OUT / "recovery_v3_run_snapshot.json"

VALID_VERDICTS = {"REJECT", "RESEARCH-ONLY", "CANDIDATE FOR REAL-CHAIN TESTING"}

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

V1_OUTPUTS = [
    DATA_OUT / "options_overlay_trades.csv",
    DATA_OUT / "options_overlay_metrics.csv",
    DATA_OUT / "baseline_vs_options_equity.csv",
    DATA_OUT / "options_overlay_run_snapshot.json",
]

V2_OUTPUTS = [
    DATA_OUT / "options_v2_trades.csv",
    DATA_OUT / "options_v2_metrics.csv",
    DATA_OUT / "options_v2_baseline_vs_overlay_equity.csv",
    DATA_OUT / "options_v2_run_snapshot.json",
]

RECOVERY_OUTPUTS = [
    DATA_OUT / "recovery_options_trades.csv",
    DATA_OUT / "recovery_options_metrics.csv",
    DATA_OUT / "recovery_baseline_vs_overlay_equity.csv",
    DATA_OUT / "recovery_run_snapshot.json",
]

V3_REQUIRED = [
    DATA_OUT / "recovery_v3_trades.csv",
    DATA_OUT / "recovery_v3_metrics.csv",
    DATA_OUT / "recovery_v3_signal_diagnostics.csv",
    DATA_OUT / "recovery_v3_entry_timing_diagnostics.csv",
    DATA_OUT / "recovery_v3_profit_taking_comparison.csv",
    DATA_OUT / "recovery_v3_baseline_vs_overlay_equity.csv",
    DATA_OUT / "recovery_v3_tactical_etf_comparison.csv",
    DATA_OUT / "recovery_v3_run_snapshot.json",
    DOCS_OUT / "options_convexity_recovery_v3_research_plan.md",
    DOCS_OUT / "options_convexity_recovery_v3_report.md",
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


def check_preserved(cr: CheckResult, label: str, paths: list[Path]) -> None:
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.exists()]
    cr.check(f"{label}_preserved", not missing, "all present" if not missing else f"missing: {missing}")


def check_required_outputs(cr: CheckResult) -> None:
    missing = [str(p.relative_to(ROOT)) for p in V3_REQUIRED if not p.exists()]
    cr.check("v3_required_outputs_exist", not missing, "all present" if not missing else f"missing: {missing}")


def check_trade_scope_and_prices(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("trade_scope_and_prices", False, "v3 trades are empty")
        return
    bad_underlyings = sorted(set(trades["underlying"].astype(str)) - set(sig.V3_UNDERLYINGS))
    bad_profit = sorted(set(trades["profit_variant"].astype(str)) - set(bt.PROFIT_VARIANTS))
    bad_dte = []
    for _, row in trades.iterrows():
        bucket = str(row["dte_bucket"])
        if bucket not in bt.DTE_BUCKETS:
            bad_dte.append((bucket, "unknown"))
            continue
        rng = bt.DTE_BUCKETS[bucket]
        if not (rng["min"] <= float(row["avg_dte"]) <= rng["max"]):
            bad_dte.append((bucket, row["avg_dte"]))
    required_numeric = ["premium_fraction", "total_budget", "trade_return", "incremental_dollars", "avg_moneyness"]
    numeric = trades[required_numeric].apply(pd.to_numeric, errors="coerce")
    bad_numeric = numeric.isna().any(axis=1) | (numeric["premium_fraction"] <= 0) | (numeric["total_budget"] <= 0)
    ok = not bad_underlyings and not bad_profit and not bad_dte and not bool(bad_numeric.any())
    cr.check(
        "trade_scope_and_prices",
        ok,
        "SPY/QQQ only; profit variants, DTE, and economics valid"
        if ok
        else f"bad_underlyings={bad_underlyings}, bad_profit={bad_profit}, bad_dte={bad_dte[:5]}, bad_numeric={int(bad_numeric.sum())}",
    )


def check_sizing_caps(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("sizing_caps", False, "no trades")
        return
    failures = []
    for variant, sub in trades.groupby("variant"):
        premium = pd.to_numeric(sub["premium_fraction"], errors="coerce")
        per_trade_max = float(premium.max())
        by_year = sub.assign(year=pd.to_datetime(sub["open_date"]).dt.year).groupby("year")["premium_fraction"].sum()
        annual_max = float(by_year.max()) if len(by_year) else 0.0
        events: list[tuple[pd.Timestamp, int, float]] = []
        for _, row in sub.iterrows():
            # Conservative: count the full staged position from pilot date.
            events.append((pd.Timestamp(row["open_date"]), 1, float(row["premium_fraction"])))
            events.append((pd.Timestamp(row["exit_date"]), 0, -float(row["premium_fraction"])))
        events.sort(key=lambda e: (e[0], e[1]))
        running = concurrent_max = 0.0
        for _, _, delta in events:
            running += delta
            concurrent_max = max(concurrent_max, running)
        if per_trade_max > bt.INTENDED_RISK + 1e-9 or annual_max > bt.MAX_ANNUAL_RISK + 1e-9 or concurrent_max > bt.MAX_CONCURRENT_RISK + 1e-9:
            failures.append((variant, per_trade_max, annual_max, concurrent_max))
    cr.check("sizing_caps", not failures, "all variant caps respected" if not failures else f"failures: {failures[:5]}")


def check_trades_respect_rules(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("trades_respect_v3_rules", False, "no trades")
        return
    signals = sig.build_recovery_v3_signals()
    states = option_data.load_market_states()["market_state"].astype(str)
    prices = option_data.load_weekly_prices(sig.V3_UNDERLYINGS)
    weights = option_data.load_baseline_weights()
    weight_chg = weights - weights.shift(4)
    violations = []

    for _, row in trades.iterrows():
        cfg = bt.V3Config(
            dte_bucket=str(row["dte_bucket"]),
            moneyness_bucket=str(row["moneyness_bucket"]),
            profit_variant=str(row["profit_variant"]),
        )
        ticker = str(row["underlying"])
        pilot_date = pd.Timestamp(row["open_date"])
        features = signals.feature_row(pilot_date, ticker)
        structure, _ = bt._price_call_structure(float(row["pilot_spot"]), features, cfg.representative_dte, cfg.otm)
        decision = sig.evaluate_stage1_entry(
            features,
            market_state=str(states.loc[pilot_date]),
            baseline_weight=_get(weights, pilot_date, ticker, 0.0),
            baseline_weight_change_4w=_get(weight_chg, pilot_date, ticker, 0.0),
            breakeven_move=structure.breakeven_move,
            holding_weeks=cfg.holding_weeks,
        )
        if not decision.active:
            violations.append((str(pilot_date.date()), ticker, "stage1", decision.reasons_failed))

        add_date = pd.to_datetime(row.get("add_date"), errors="coerce")
        if pd.notna(add_date):
            features2 = signals.feature_row(add_date, ticker)
            try:
                add_spot = float(prices.loc[add_date, ticker])
            except Exception:
                add_spot = np.nan
            if not np.isfinite(add_spot):
                violations.append((str(add_date.date()), ticker, "stage2", "missing spot"))
                continue
            structure2, _ = bt._price_call_structure(add_spot, features2, cfg.representative_dte, cfg.otm)
            weeks_since = int((prices.index.get_loc(add_date) - prices.index.get_loc(pilot_date)))
            decision2 = sig.evaluate_stage2_addon(
                features2,
                market_state=str(states.loc[add_date]),
                breakeven_move=structure2.breakeven_move,
                holding_weeks=cfg.holding_weeks,
                weeks_since_pilot=weeks_since,
                max_add_window_weeks=bt.ADD_WINDOW_WEEKS,
            )
            if not decision2.active:
                violations.append((str(add_date.date()), ticker, "stage2", decision2.reasons_failed))
    cr.check(
        "trades_respect_v3_rules",
        not violations,
        f"all {len(trades)} trades replay through v3 gates" if not violations else f"{len(violations)} violations: {violations[:5]}",
    )


def check_diagnostics(cr: CheckResult) -> None:
    timing_path = DATA_OUT / "recovery_v3_entry_timing_diagnostics.csv"
    profit_path = DATA_OUT / "recovery_v3_profit_taking_comparison.csv"
    if not timing_path.exists() or not profit_path.exists():
        cr.check("diagnostics_present", False, "timing or profit diagnostics missing")
        return
    timing = pd.read_csv(timing_path)
    profit = pd.read_csv(profit_path)
    timing_ok = {"summary", "stage", "late_entry_reason"}.issubset(set(timing["section"].astype(str)))
    profit_have = set(profit["profit_variant"].astype(str))
    profit_ok = {"no_target", "full_100", "partial_runner"}.issubset(profit_have)
    cr.check(
        "diagnostics_present",
        timing_ok and profit_ok,
        f"timing sections ok={timing_ok}; profit variants={sorted(profit_have)}",
    )


def check_exit_rules(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("exit_rules_valid", False, "no trades")
        return
    allowed_prefixes = [
        "time_stop",
        "thesis_invalidated",
        "underlying_trailing_failure",
        "runner_giveback",
        "full_profit_target",
        "data_end",
    ]
    bad_reason = [r for r in trades["exit_reason"].astype(str) if not any(r.startswith(p) for p in allowed_prefixes)]
    bad_hold = []
    for _, row in trades.iterrows():
        if float(row["weeks_held"]) * 7.0 > float(row["avg_dte"]) + 7.0:
            bad_hold.append((row["variant"], row["weeks_held"], row["avg_dte"]))
    cr.check("exit_rules_valid", not bad_reason and not bad_hold, "exit reasons and holding windows valid" if not bad_reason and not bad_hold else f"bad_reason={bad_reason[:5]}, bad_hold={bad_hold[:5]}")


def check_no_lookahead(cr: CheckResult) -> None:
    prices = option_data.load_weekly_prices(sig.V3_UNDERLYINGS)
    unlagged = prices.pct_change(12)
    signals = sig.build_recovery_v3_signals()
    lagged = signals.per_ticker["ret_12w"].dropna(how="all")
    shifted = unlagged.shift(1).reindex(lagged.index)
    matches = np.isclose(lagged.values, shifted.values, equal_nan=True)
    cr.check("no_lookahead", bool(matches.all()), "ret_12w equals prior-week value" if matches.all() else "ret_12w lag mismatch")


def check_metrics_present(cr: CheckResult) -> None:
    path = DATA_OUT / "recovery_v3_metrics.csv"
    if not path.exists():
        cr.check("metrics_present", False, "metrics file missing")
        return
    m = pd.read_csv(path)
    strategies = set(m["strategy"].astype(str))
    variants = set(m["variant"].astype(str))
    metrics_have = set(m["metric"].astype(str))
    required_strategies = {"baseline", "v3_options", "tactical_tilt"}
    required_metrics = {
        "cagr",
        "ann_return",
        "ann_vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "cvar_1",
        "option_hit_rate",
        "avg_trade_return",
        "median_trade_return",
        "worst_trade_return",
        "best_trade_return",
        "sharpe_ex_best",
        "sharpe_ex_top3",
        "premium_at_risk_per_year",
        "max_concurrent_risk",
        "addon_success_rate",
        "partial_trigger_rate",
        "late_entry_block_rate",
        "runner_avg_return",
        "options_minus_tilt_sharpe",
    }
    ok = required_strategies.issubset(strategies) and "prior_recovery_main" in variants and required_metrics.issubset(metrics_have)
    cr.check(
        "metrics_present",
        ok,
        "baseline/v3/tactical/prior recovery metrics present"
        if ok
        else f"strategies={strategies}, prior={'prior_recovery_main' in variants}, missing_metrics={sorted(required_metrics - metrics_have)}",
    )


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
    robust = gates.get("sharpe_ex_best_ok", {}).get("pass", False) and gates.get("sharpe_ex_top3_ok", {}).get("pass", False)
    cr.check(
        "top_trade_break_not_promoted",
        robust or verdict != "CANDIDATE FOR REAL-CHAIN TESTING",
        "fragile result not promoted" if not robust else "robustness gates pass",
    )
    caveat_ok = "PROXY RESULTS" in report and "Real historical option-chain data is required" in report
    cr.check("proxy_caveat_present", caveat_ok, "real-chain caveat present")


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
    print("[verify v3] Recovery Options Overlay v3 outputs\n")
    cr = CheckResult()
    trades_path = DATA_OUT / "recovery_v3_trades.csv"
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    check_production_untouched(cr)
    check_preserved(cr, "v1_outputs", V1_OUTPUTS)
    check_preserved(cr, "v2_outputs", V2_OUTPUTS)
    check_preserved(cr, "prior_recovery_outputs", RECOVERY_OUTPUTS)
    check_required_outputs(cr)
    check_trade_scope_and_prices(cr, trades)
    check_sizing_caps(cr, trades)
    check_trades_respect_rules(cr, trades)
    check_diagnostics(cr)
    check_exit_rules(cr, trades)
    check_no_lookahead(cr)
    check_metrics_present(cr)
    check_verdict(cr)

    print(f"\n[verify v3] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify v3] FAILURES:")
        for failure in cr.failed:
            print(f"  - {failure}")
        return 1
    print("[verify v3] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
