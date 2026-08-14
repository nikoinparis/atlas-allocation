"""Verifier for the v2 Options Convexity Overlay research extension.

Runs independent safety / integrity checks AFTER the v2 runner. Exits non-zero
if any check fails.

Checks
------
1.  Production files were NOT modified.
2.  v1 outputs are preserved (still present).
3.  v2 required outputs exist.
4.  Options premium allocation never exceeds the 3% hard cap (per-trade + concurrent).
5.  v2 trades only occur when the v2 activation rules actually pass.
6.  No negative / invalid option prices or payoffs.
7.  No look-ahead bias in signal usage (signals strictly lagged).
8.  DTE bucket labels are valid and DTE days fall within the bucket range.
9.  Metrics output includes the required risk fields.
10. Report contains a clear final verdict (REJECT / RESEARCH-ONLY / CANDIDATE FOR FURTHER TESTING).
11. Default verdict is RESEARCH-ONLY unless all gates pass.
12. If Sharpe improves only because of one best trade, the verdict is not promoted.
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
    options_dte_sweep,
    options_signal_engine_v2,
    options_v2_backtest,
)

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_v2_research_report.md"
SNAPSHOT_PATH = DATA_OUT / "options_v2_run_snapshot.json"

HARD_CAP = options_v2_backtest.HARD_CAP_TOTAL_PREMIUM
VALID_VERDICTS = {"REJECT", "RESEARCH-ONLY", "CANDIDATE FOR FURTHER TESTING"}

PROTECTED_PATHS = [
    "scripts/production_config.py",
    "scripts/production_metrics.py",
    "scripts/production_costs.py",
    "scripts/production_allocator.py",
    "scripts/reproduce_production_candidate.py",
    "data/05_layer3_portfolio_construction/portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv",
    "data/04_layer2b_risk_regime_engine/market_state_history.csv",
    "data/01_data_hub/weekly_prices.csv",
]

V1_OUTPUTS = [
    DATA_OUT / "options_overlay_trades.csv",
    DATA_OUT / "options_overlay_metrics.csv",
    DATA_OUT / "baseline_vs_options_equity.csv",
    DATA_OUT / "options_overlay_run_snapshot.json",
    DOCS_OUT / "options_convexity_research_report.md",
]

V2_REQUIRED = [
    DATA_OUT / "options_v2_trades.csv",
    DATA_OUT / "options_v2_metrics.csv",
    DATA_OUT / "options_v2_dte_sweep.csv",
    DATA_OUT / "options_v2_signal_diagnostics.csv",
    DATA_OUT / "options_v2_baseline_vs_overlay_equity.csv",
    DATA_OUT / "options_v2_run_snapshot.json",
    DOCS_OUT / "options_convexity_v2_research_plan.md",
    DOCS_OUT / "options_convexity_v2_research_report.md",
]


class CheckResult:
    def __init__(self):
        self.passed, self.failed = [], []

    def check(self, name, ok, detail=""):
        line = f"{name}: {detail}".strip()
        (self.passed if ok else self.failed).append(line)
        print(f"  [{'PASS' if ok else 'FAIL'}] {line}")

    @property
    def all_ok(self):
        return not self.failed


def check_production_untouched(cr):
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except Exception as exc:  # pragma: no cover
        cr.check("production_untouched", False, f"git status failed: {exc}")
        return
    modified = set()
    for line in out.splitlines():
        status, path = line[:2], line[3:].strip()
        if status.strip() and status != "??":
            modified.add(path)
    touched = [p for p in PROTECTED_PATHS if p in modified]
    cr.check("production_untouched", not touched,
             "no protected production files modified" if not touched else f"MODIFIED: {touched}")


def check_v1_preserved(cr):
    missing = [str(p.relative_to(ROOT)) for p in V1_OUTPUTS if not p.exists()]
    cr.check("v1_outputs_preserved", not missing,
             "all v1 outputs present" if not missing else f"missing: {missing}")


def check_v2_required(cr):
    missing = [str(p.relative_to(ROOT)) for p in V2_REQUIRED if not p.exists()]
    cr.check("v2_required_outputs_exist", not missing,
             "all present" if not missing else f"missing: {missing}")


def check_allocation_cap(cr, trades):
    if trades.empty:
        cr.check("allocation_within_cap", True, "no trades (vacuously within cap)")
        return
    per_trade_max = float(trades["premium_fraction"].max())
    events = []
    for _, t in trades.iterrows():
        events.append((pd.Timestamp(t["open_date"]), float(t["premium_fraction"])))
        events.append((pd.Timestamp(t["expiry_date"]), -float(t["premium_fraction"])))
    # Closes free capital before opens reuse it on the same date.
    events.sort(key=lambda e: (e[0], e[1]))
    running = concurrent_max = 0.0
    for _, delta in events:
        running += delta
        concurrent_max = max(concurrent_max, running)
    ok = per_trade_max <= HARD_CAP + 1e-9 and concurrent_max <= HARD_CAP + 1e-9
    cr.check("allocation_within_cap", ok,
             f"per-trade max {per_trade_max:.4f}, concurrent max {concurrent_max:.4f}, cap {HARD_CAP}")


def check_trades_respect_rules(cr, trades):
    if trades.empty:
        cr.check("trades_respect_rules", True, "no trades to check")
        return
    signals = options_signal_engine_v2.build_v2_signals()
    states = option_data.load_market_states()
    baseline_weights = option_data.load_baseline_weights()

    violations = []
    for _, t in trades.iterrows():
        d = pd.Timestamp(t["open_date"])
        ticker = t["underlying"]
        level = int(t["ablation_level"])
        if d not in states.index:
            violations.append((str(d.date()), ticker, "date not in states"))
            continue
        features = signals.feature_row(d, ticker)
        # Rebuild the same structure at entry to recover the breakeven move.
        spot = float(t["open_spot"])
        sigma = float(t["sigma"])
        dte_days = float(t["dte_days"])
        structure = options_dte_sweep.build_structure(str(t["structure"]), spot, sigma, dte_days,
                                                      options_v2_backtest.RISK_FREE_RATE)
        net_premium = options_dte_sweep.price_structure(structure, risk_free_rate=options_v2_backtest.RISK_FREE_RATE)
        entry_cost = net_premium * (1.0 + options_v2_backtest.ENTRY_SLIPPAGE_PCT + options_v2_backtest.HALF_SPREAD_PROXY)
        be_move = options_dte_sweep.breakeven_move(structure, entry_cost)
        horizon = max(int(round(dte_days / 7.0)), 1)

        st = states.loc[d]
        decision = options_signal_engine_v2.evaluate_v2_entry(
            features, level=level, market_state=str(st["market_state"]),
            market_drawdown=float(pd.to_numeric(st.get("market_drawdown"), errors="coerce") or 0.0),
            baseline_weight=_get(baseline_weights, d, ticker, 0.0),
            breakeven_move=be_move, horizon_weeks=horizon,
            iv_history_available=np.isfinite(features.get("vol_percentile", np.nan)),
        )
        if not decision.active:
            violations.append((str(d.date()), ticker, decision.reasons_failed))

    cr.check("trades_respect_rules", not violations,
             f"all {len(trades)} trades pass v2 rules" if not violations
             else f"{len(violations)} violations: {violations[:5]}")


def check_valid_prices(cr, trades):
    if trades.empty:
        cr.check("valid_option_prices", True, "no trades to check")
        return
    bad = trades[
        (trades["entry_cost_per_share"] <= 0)
        | (~np.isfinite(trades["entry_cost_per_share"]))
        | (trades["final_intrinsic"] < 0)
        | (~np.isfinite(trades["final_intrinsic"]))
        | (trades["long_strike"] <= 0)
    ]
    cr.check("valid_option_prices", bad.empty,
             "all premiums/payoffs valid" if bad.empty else f"{len(bad)} invalid rows")


def check_no_lookahead(cr):
    prices = option_data.load_weekly_prices()
    unlagged_12 = prices.pct_change(12)
    signals = options_signal_engine_v2.build_v2_signals()
    lagged_12 = signals.per_ticker["ret_12w"]
    aligned = lagged_12.dropna(how="all")
    shifted = unlagged_12.shift(1).reindex(aligned.index)
    matches = np.isclose(aligned.values, shifted.values, equal_nan=True)
    cr.check("no_lookahead_signals", bool(matches.all()),
             "ret_12w equals prior-week (lag=1) value — causal" if matches.all()
             else "lagged signal != shift(1) — possible look-ahead")


def check_dte_labels(cr, trades):
    if trades.empty:
        cr.check("dte_labels_valid", True, "no trades to check")
        return
    bad = []
    for _, t in trades.iterrows():
        bucket = str(t["dte_bucket"])
        if bucket not in options_dte_sweep.DTE_BUCKETS:
            bad.append((bucket, "unknown bucket"))
            continue
        rng = options_dte_sweep.DTE_BUCKETS[bucket]
        if not (rng["min"] <= float(t["dte_days"]) <= rng["max"]):
            bad.append((bucket, f"dte {t['dte_days']} outside {rng['min']}-{rng['max']}"))
    cr.check("dte_labels_valid", not bad, "all DTE labels valid" if not bad else f"{bad[:5]}")


def check_metrics_present(cr):
    path = DATA_OUT / "options_v2_metrics.csv"
    if not path.exists():
        cr.check("key_metrics_present", False, "metrics file missing")
        return
    have = set(pd.read_csv(path)["metric"].unique())
    required = {"cagr", "ann_return", "ann_vol", "sharpe", "sortino", "max_drawdown",
                "calmar", "cvar_5", "option_hit_rate", "avg_trade_return", "median_trade_return",
                "worst_trade_return", "best_trade_return", "sharpe_ex_best",
                "premium_spent_per_year", "activations_per_year", "avg_dte", "avg_moneyness"}
    missing = sorted(required - have)
    cr.check("key_metrics_present", not missing, "all key risk metrics present" if not missing else f"missing: {missing}")


def check_verdict(cr):
    if not REPORT_PATH.exists():
        cr.check("report_has_verdict", False, "report missing")
        return
    text = REPORT_PATH.read_text()
    found = [v for v in VALID_VERDICTS if v in text]
    cr.check("report_has_verdict", bool(found), f"verdict(s): {found}" if found else "no verdict")

    if SNAPSHOT_PATH.exists():
        snap = json.loads(SNAPSHOT_PATH.read_text())
        verdict = snap.get("verdict")
        gates = snap.get("gates", {})
        all_pass = all(g.get("pass") for g in gates.values()) if gates else False
        if all_pass:
            ok = verdict == "CANDIDATE FOR FURTHER TESTING"
            detail = f"all gates pass -> {verdict}"
        else:
            ok = verdict in {"RESEARCH-ONLY", "REJECT"}
            detail = f"not all gates pass -> {verdict} (must be RESEARCH-ONLY/REJECT)"
        cr.check("verdict_default_consistent", ok, detail)

        # One-best-trade safeguard.
        not_one_trade_ok = gates.get("not_one_trade", {}).get("pass", False)
        ex_best_ok = gates.get("sharpe_ex_best_acceptable", {}).get("pass", False)
        if not (not_one_trade_ok and ex_best_ok):
            cr.check("one_trade_not_promoted", verdict != "CANDIDATE FOR FURTHER TESTING",
                     f"edge leans on best trade -> verdict {verdict} (must not be CANDIDATE)")
        else:
            cr.check("one_trade_not_promoted", True, "edge survives best-trade removal")


def _get(df, date, ticker, default=np.nan):
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
    print("[verify v2] Options Convexity Overlay v2 outputs\n")
    cr = CheckResult()
    trades_path = DATA_OUT / "options_v2_trades.csv"
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    check_production_untouched(cr)
    check_v1_preserved(cr)
    check_v2_required(cr)
    check_allocation_cap(cr, trades)
    check_trades_respect_rules(cr, trades)
    check_valid_prices(cr, trades)
    check_no_lookahead(cr)
    check_dte_labels(cr, trades)
    check_metrics_present(cr)
    check_verdict(cr)

    print(f"\n[verify v2] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify v2] FAILURES:")
        for f in cr.failed:
            print(f"  - {f}")
        return 1
    print("[verify v2] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
