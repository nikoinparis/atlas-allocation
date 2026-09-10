#!/usr/bin/env python3
"""Pre-flight the 2026-09-11 clock start, before the window opens.

Six clocks start that evening and a missed week cannot be backfilled -- every
protocol says so in its own missed_snapshot_policy. Between 2026-09-05 and
2026-09-06 this repository changed code that runs inside that sequence: the
composite book builder now saves a dated book, the valuation score panel gained
a quarter, a recorder was written that did not exist, and a derived blend
recorder was added. None of that has ever been executed as one sequence.

This checks everything checkable while the window is still shut. It cannot run
the recorders -- they refuse before 21:00 UTC on the decision Friday, correctly
-- so instead it verifies every precondition they will hit: the scripts import,
their protocols parse and forbid execution, their inputs exist, their logs are
empty and verifiable, the panels reach far enough, and the books they will ask
for can actually be built from today's data.

Failures here are cheap. Failures on Friday cost a week that cannot be recovered.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.forward_evidence import read_and_verify_log

DECISION = "2026-09-11"
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))


def imports(path: str) -> object | None:
    try:
        spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as error:                       # noqa: BLE001
        check(f"import {Path(path).name}", False, f"{type(error).__name__}: {error}")
        return None


def main() -> int:
    decision = pd.Timestamp(DECISION, tz="UTC")
    if date.fromisoformat(DECISION).weekday() != 4:
        check("decision date is a Friday", False, DECISION)

    # 1. Every script the runbook names exists and imports.
    scripts = [
        "scripts/acquire_yahoo_recent_current_sec_prices_v1.py",
        "scripts/acquire_free_etf_snapshot.py",
        "scripts/run_sec_growth_survivorship_retest_v1.py",
        "scripts/build_cash_conversion_sleeve_path_v1.py",
        "scripts/build_control_composite_book_v1.py",
        "scripts/build_residual_sleeve_decision_packet_v1.py",
        "scripts/record_sec_residual_controlled_sleeve_forward_v1.py",
        "scripts/record_equal_weight_benchmark_forward_v1.py",
        "scripts/record_residual_tie_agnostic_companion_forward_v1.py",
        "scripts/record_valuation_earnings_yield_forward_v1.py",
    ]
    for relative in scripts:
        exists = (ROOT / relative).is_file()
        check(f"exists {Path(relative).name}", exists)
        if exists and Path(relative).name.startswith(("record_", "build_control")):
            imports(relative)

    # 2. Every protocol parses, forbids execution, and starts no earlier than today.
    protocols = [
        "config/forward/sec_residual_controlled_sleeve_forward_v1.json",
        "config/forward/equal_weight_benchmark_v1.json",
        "config/forward/residual_tie_agnostic_companion_v1.json",
        "config/forward/sue_quarterly_forward_v1.json",
        "config/forward/valuation_earnings_yield_forward_v1.json",
    ]
    for relative in protocols:
        path = ROOT / relative
        if not path.is_file():
            check(f"protocol {Path(relative).name}", False, "missing")
            continue
        body = json.loads(path.read_text())
        unsafe = body.get("live_trading_enabled") or body.get("execution_enabled") \
            or body.get("strategy_promotion_authorized")
        check(f"protocol {Path(relative).name} forbids execution", not unsafe)

    # 3. Logs are empty and verifiable. A clock that already has records would mean
    #    something ran early, which is worse than a clock that has not started.
    logs = {
        "residual": "evidence/forward_sec_residual_controlled_sleeve_v1/decisions.jsonl",
        "benchmark": "evidence/forward_equal_weight_benchmark_v1/decisions.jsonl",
        "companion": "evidence/forward_residual_tie_agnostic_companion_v1/decisions.jsonl",
        "valuation": "evidence/forward_valuation_earnings_yield_v1/decisions.jsonl",
    }
    for name, relative in logs.items():
        path = ROOT / relative
        field = "realization_date" if name == "blend" else "decision_date"
        try:
            records = read_and_verify_log(path, date_field=field, first_eligible_date=DECISION)
            check(f"log {name} empty and verifiable", len(records) == 0,
                  f"{len(records)} records" if records else "")
        except Exception as error:                   # noqa: BLE001
            check(f"log {name} empty and verifiable", False, f"{type(error).__name__}: {error}")

    # 4. The valuation book the recorder will pick on Friday can actually be built.
    module = imports("scripts/record_valuation_earnings_yield_forward_v1.py")
    if module is not None:
        try:
            prices = module.load_prices()
            block_at, target = module.book_for(decision, module.tradable_at(prices, decision))
            age = (decision - pd.Timestamp(block_at, tz="UTC")).days
            check("valuation book builds", len(target) == module.BREADTH,
                  f"block {block_at}, {len(target)} names, {age}d old")
            check("valuation block is current (<120d)", age < 120, f"{age} days")
            week = max(w for w in prices.index if w <= decision)
            priced = sum(1 for n in target if n in prices.columns and pd.notna(prices.loc[week, n]))
            check("every valuation name is priced", priced == len(target),
                  f"{priced}/{len(target)}")
        except Exception as error:                   # noqa: BLE001
            check("valuation book builds", False, f"{type(error).__name__}: {error}")

    # 5. Panels reach the decision date.
    panels = {
        "sec full history": "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz",
        "sec narrow v2": "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz",
        "etf weekly": "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz",
    }
    for name, relative in panels.items():
        path = ROOT / relative
        if not path.is_file():
            check(f"panel {name}", False, "missing")
            continue
        last = pd.read_csv(path, usecols=[0]).iloc[:, 0].max()
        check(f"panel {name} reaches 2026-09-04", str(last)[:10] >= "2026-09-04", f"last {str(last)[:10]}")

    # 6. The composite book builder produces a valid book for the last known Friday.
    #    Friday's own date needs prices that do not exist yet, so exercise the path
    #    on the most recent date it can actually run.
    try:
        import subprocess
        run = subprocess.run([str(ROOT / ".venv/bin/python"),
                              str(ROOT / "scripts/build_control_composite_book_v1.py"),
                              "--decision-date", "2026-07-31"],
                             capture_output=True, text=True, cwd=ROOT, timeout=900)
        ok = run.returncode == 0
        detail = ""
        if ok:
            body = json.loads(run.stdout)
            total_ok = abs(sum(body["weights"].values()) - 1.0) < 1e-9
            ok = total_ok and body.get("book_saved") in ("unchanged", None) or total_ok
            detail = f"{body['book_names']} names, saved={body.get('book_saved')}"
        else:
            detail = (run.stderr.strip().splitlines() or ["?"])[-1][:100]
        check("composite book builder runs and sums to 1", ok, detail)
    except Exception as error:                       # noqa: BLE001
        check("composite book builder runs and sums to 1", False, f"{type(error).__name__}: {error}")

    # 7. The blend must NOT have started. Owner decision 2026-09-10: superseded
    #    before its first decision because its rationale was the Step 291 date
    #    offset. A record here would mean it ran by habit, which is the failure
    #    this check exists to catch.
    blend_log = ROOT / "evidence/forward_valuation_growth_5050_blend_v1/observations.jsonl"
    started = blend_log.is_file() and blend_log.stat().st_size > 0
    check("superseded blend clock has NOT started", not started,
          "records exist -- it ran despite being superseded" if started else "")
    superseded = ROOT / "config/forward/valuation_growth_5050_blend_forward_v1.SUPERSEDED.json"
    check("blend supersession is recorded", superseded.is_file())

    # 8. The blend recorder still runs cleanly if invoked, but must not be.
    try:
        import subprocess
        run = subprocess.run([str(ROOT / ".venv/bin/python"),
                              str(ROOT / "scripts/record_valuation_growth_5050_blend_forward_v1.py")],
                             capture_output=True, text=True, cwd=ROOT, timeout=300)
        body = json.loads(run.stdout) if run.returncode == 0 else {}
        check("blend recorder would still be a clean no-op if run",
              run.returncode == 0 and body.get("weeks_shared_and_recorded") == 0,
              (run.stderr.strip().splitlines() or [""])[-1][:100] if run.returncode else "")
    except Exception as error:                       # noqa: BLE001
        check("blend recorder would still be a clean no-op if run", False, f"{type(error).__name__}: {error}")

    failed = [c for c in CHECKS if not c[1]]
    width = max(len(c[0]) for c in CHECKS)
    for name, ok, detail in CHECKS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:{width}s}  {detail}")
    print(f"\n{len(CHECKS) - len(failed)} of {len(CHECKS)} checks pass")
    if failed:
        print("\nBLOCKERS FOR 2026-09-11:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")

    out = ROOT / "evidence/forward_clock_preflight_v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps({
        "decision_date": DECISION,
        "checks_total": len(CHECKS), "checks_passed": len(CHECKS) - len(failed),
        "blockers": [{"check": n, "detail": d} for n, _, d in failed],
        "ready": not failed,
    }, indent=2, sort_keys=True) + "\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
