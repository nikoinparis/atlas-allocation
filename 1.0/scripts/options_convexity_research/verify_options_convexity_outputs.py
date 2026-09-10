"""Verifier for the Options Convexity Overlay research experiment.

Runs a battery of independent safety / integrity checks AFTER the research
script has produced its outputs. Exits non-zero if any check fails, so it can
be used as a guard in CI or before sharing results.

Checks performed
----------------
1. Production files were NOT modified by this experiment.
2. All required output files exist.
3. Options allocation never exceeds the 3% hard cap (per-trade and concurrent).
4. Option trades only occur when the activation rules actually pass.
5. No negative or invalid option prices / premiums.
6. No look-ahead bias in signal usage (signals are strictly lagged).
7. No missing key metrics in the metrics output.
8. The report contains a clear final verdict (REJECT / RESEARCH-ONLY /
   CANDIDATE FOR FURTHER TESTING).
9. The verdict defaults to RESEARCH-ONLY unless all gates pass.
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

from options_convexity import option_data, overlay_rules  # noqa: E402

DATA_OUT = ROOT / "data" / "research" / "options_convexity"
DOCS_OUT = ROOT / "docs" / "research" / "options_convexity"
REPORT_PATH = DOCS_OUT / "options_convexity_research_report.md"
SNAPSHOT_PATH = DATA_OUT / "options_overlay_run_snapshot.json"

HARD_CAP = overlay_rules.HARD_CAP_TOTAL_PREMIUM
VALID_VERDICTS = {"REJECT", "RESEARCH-ONLY", "CANDIDATE FOR FURTHER TESTING"}

# Production artifacts/areas this experiment must never modify.
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


class CheckResult:
    def __init__(self):
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
    """Ensure protected production files have no working-tree modifications."""

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception as exc:  # pragma: no cover - git absent
        cr.check("production_untouched", False, f"git status failed: {exc}")
        return

    modified = set()
    for line in out.splitlines():
        # Porcelain format: XY <path>. Anything not untracked ('??') is a change.
        status, _, path = line[:2], line[2:3], line[3:].strip()
        if status.strip() and status != "??":
            modified.add(path)

    touched = [p for p in PROTECTED_PATHS if p in modified]
    cr.check(
        "production_untouched",
        len(touched) == 0,
        "no protected production files modified" if not touched else f"MODIFIED: {touched}",
    )


def check_required_outputs(cr: CheckResult) -> None:
    required = [
        DATA_OUT / "options_overlay_trades.csv",
        DATA_OUT / "options_overlay_metrics.csv",
        DATA_OUT / "baseline_vs_options_equity.csv",
        DOCS_OUT / "options_convexity_research_plan.md",
        DOCS_OUT / "options_convexity_research_report.md",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    cr.check("required_outputs_exist", not missing, "all present" if not missing else f"missing: {missing}")


def check_allocation_cap(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("allocation_within_cap", True, "no trades (vacuously within cap)")
        return

    # Per-trade premium fraction never exceeds the hard cap.
    per_trade_max = float(trades["premium_fraction"].max())

    # Concurrent exposure: sum of premium fractions of trades whose [open,expiry]
    # windows overlap. Compute the running concurrent maximum by sweeping events.
    events = []
    for _, t in trades.iterrows():
        events.append((pd.Timestamp(t["open_date"]), float(t["premium_fraction"])))
        events.append((pd.Timestamp(t["expiry_date"]), -float(t["premium_fraction"])))
    # On the same date, process closes (negative delta) BEFORE opens: an
    # expiring spread settles and frees its premium budget before a new spread
    # can reuse that capital the same week, matching the backtest's accounting.
    events.sort(key=lambda e: (e[0], e[1]))
    running = 0.0
    concurrent_max = 0.0
    for _, delta in events:
        running += delta
        concurrent_max = max(concurrent_max, running)

    ok = per_trade_max <= HARD_CAP + 1e-9 and concurrent_max <= HARD_CAP + 1e-9
    cr.check(
        "allocation_within_cap",
        ok,
        f"per-trade max {per_trade_max:.4f}, concurrent max {concurrent_max:.4f}, cap {HARD_CAP}",
    )


def check_trades_only_when_rules_pass(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("trades_respect_rules", True, "no trades to check")
        return

    prices = option_data.load_weekly_prices()
    baseline_weights = option_data.load_baseline_weights()
    states = option_data.load_market_states()
    trend = option_data.build_trend_signals(prices)
    iv_proxy = option_data.build_iv_proxy(prices)
    iv_pct = option_data.iv_percentile(iv_proxy)

    violations = []
    for _, t in trades.iterrows():
        d = pd.Timestamp(t["open_date"])
        ticker = t["underlying"]
        if d not in states.index:
            violations.append((d, ticker, "open_date not in state index"))
            continue
        st = states.loc[d]
        decision = overlay_rules.evaluate_activation(
            ticker,
            market_state=str(st["market_state"]),
            market_drawdown=float(pd.to_numeric(st.get("market_drawdown"), errors="coerce") or 0.0),
            mom_13w=_get(trend["mom_13w"], d, ticker),
            mom_26w=_get(trend["mom_26w"], d, ticker),
            above_sma=_get(trend["above_sma_40w"], d, ticker),
            baseline_weight=_get(baseline_weights, d, ticker, 0.0),
            iv_pct=_get(iv_pct, d, ticker),
            liquidity_ok=True,
            iv_history_available=np.isfinite(_get(iv_pct, d, ticker)),
        )
        if not decision.active:
            violations.append((str(d.date()), ticker, decision.reasons_failed))

    cr.check(
        "trades_respect_rules",
        not violations,
        f"all {len(trades)} trades pass activation rules"
        if not violations
        else f"{len(violations)} rule violations: {violations[:5]}",
    )


def check_valid_prices(cr: CheckResult, trades: pd.DataFrame) -> None:
    if trades.empty:
        cr.check("valid_option_prices", True, "no trades to check")
        return
    bad = trades[
        (trades["entry_cost_per_share"] <= 0)
        | (trades["final_intrinsic"] < 0)
        | (~np.isfinite(trades["entry_cost_per_share"]))
        | (~np.isfinite(trades["final_intrinsic"]))
        | (trades["long_strike"] >= trades["short_strike"])
    ]
    cr.check(
        "valid_option_prices",
        bad.empty,
        "all premiums/payoffs valid and long<short" if bad.empty else f"{len(bad)} invalid rows",
    )


def check_no_lookahead(cr: CheckResult, trades: pd.DataFrame) -> None:
    """Confirm the trend signals used are strictly lagged (no same-week data)."""

    prices = option_data.load_weekly_prices()
    # Unlagged momentum (uses week-t price) vs the lagged signal the module uses.
    unlagged_13 = prices.pct_change(13)
    lagged_13 = option_data.build_trend_signals(prices)["mom_13w"]

    # Structural proof: lagged signal at date d must equal unlagged at the PRIOR
    # week, and must NOT equal the unlagged value at d (except by coincidence of
    # flat prices). We assert the shift relationship holds across the panel.
    aligned = lagged_13.dropna(how="all")
    shifted_unlagged = unlagged_13.shift(1).reindex(aligned.index)
    matches = np.isclose(aligned.values, shifted_unlagged.values, equal_nan=True)
    structural_ok = bool(matches.all())

    cr.check(
        "no_lookahead_signals",
        structural_ok,
        "trend signals equal prior-week (lag=1) values — causal"
        if structural_ok
        else "lagged signal does not match shift(1) — possible look-ahead",
    )


def check_metrics_present(cr: CheckResult) -> None:
    path = DATA_OUT / "options_overlay_metrics.csv"
    if not path.exists():
        cr.check("key_metrics_present", False, "metrics file missing")
        return
    m = pd.read_csv(path)
    have = set(m["metric"].unique())
    required = {
        "cagr",
        "ann_return",
        "ann_vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "option_hit_rate",
        "avg_trade_return",
        "median_trade_return",
        "worst_trade_return",
        "premium_spent_per_year",
        "activations_per_year",
        "incremental_cagr",
        "incremental_max_drawdown",
    }
    missing = sorted(required - have)
    cr.check("key_metrics_present", not missing, "all key metrics present" if not missing else f"missing: {missing}")


def check_verdict(cr: CheckResult) -> None:
    if not REPORT_PATH.exists():
        cr.check("report_has_verdict", False, "report missing")
        return
    text = REPORT_PATH.read_text()
    found = [v for v in VALID_VERDICTS if v in text]
    cr.check("report_has_verdict", bool(found), f"verdict(s) in report: {found}" if found else "no verdict found")

    # Default-RESEARCH-ONLY-unless-all-gates-pass consistency check.
    if SNAPSHOT_PATH.exists():
        snap = json.loads(SNAPSHOT_PATH.read_text())
        verdict = snap.get("verdict")
        gates = snap.get("gates", {})
        all_pass = all(g.get("pass") for g in gates.values()) if gates else False
        if all_pass:
            ok = verdict == "CANDIDATE FOR FURTHER TESTING"
            detail = f"all gates pass -> verdict {verdict}"
        else:
            ok = verdict in {"RESEARCH-ONLY", "REJECT"}
            detail = f"not all gates pass -> verdict {verdict} (must be RESEARCH-ONLY/REJECT)"
        cr.check("verdict_default_consistent", ok, detail)


def _get(df: pd.DataFrame, date, ticker: str, default: float = np.nan) -> float:
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
    print("[verify] Options Convexity Overlay outputs\n")
    cr = CheckResult()

    trades_path = DATA_OUT / "options_overlay_trades.csv"
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    check_production_untouched(cr)
    check_required_outputs(cr)
    check_allocation_cap(cr, trades)
    check_trades_only_when_rules_pass(cr, trades)
    check_valid_prices(cr, trades)
    check_no_lookahead(cr, trades)
    check_metrics_present(cr)
    check_verdict(cr)

    print(f"\n[verify] {len(cr.passed)} passed, {len(cr.failed)} failed")
    if not cr.all_ok:
        print("[verify] FAILURES:")
        for f in cr.failed:
            print(f"  - {f}")
        return 1
    print("[verify] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
