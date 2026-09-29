#!/usr/bin/env python3
"""Run the whole weekly forward sequence, every clock, in one command.

Three weekly windows have now lapsed (2026-08-28, 2026-09-04, 2026-09-18), and every
one was an operator gap: the code worked, nobody ran it, or somebody ran one of the
four commands and not the others. This runs all of them, in order, and is safe to
run every day of the week:

- it works out the latest decision Friday whose window is open;
- if every clock already carries that Friday's decision (and realization where one is
  due), it says so and exits 0 without touching the network;
- otherwise it runs only what is missing, fails closed on the first error, and
  never passes a date whose window has closed -- the recorders refuse those anyway.

A missed day costs nothing because the window is seven days wide; a missed week
cannot be recovered. So the scheduler runs this daily rather than once on Saturday.

Research only. Nothing here can place an order.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
PYTHON = str(ROOT / ".venv/bin/python")
PODMAN = "/opt/homebrew/bin/podman"
PODMAN_MACHINE = "portfolio-optimizer-sandbox"
RUNS = ROOT / "evidence/friday_cycle_runs"
PANELS = {
    "narrow": ROOT / "data/clean_weekly_prices_v2/manifest.json",
    "broad": ROOT / "data/broad_full_history_panel_v1/manifest.json",
}

# Every running clock. The residual sleeve is omitted on purpose: it is blocked on the
# Step 309 hardcoded-vintage decision, which is the owner's, not this script's.
ETF_CLOCKS = ["covariance_minimum_variance_v1", "breadth_confirmed_trend_return_ceiling_v3",
              "past_only_consensus_selector_return_v1", "return_first_60_40_blend_v1"]
FROZEN_BOOK_PROTOCOLS = ETF_CLOCKS[1:]
STOCK_RECORDERS = {                     # evidence directory -> recorder script
    "equal_weight_benchmark_v1": "record_equal_weight_benchmark_forward_v1.py",
    "valuation_earnings_yield_v1": "record_valuation_earnings_yield_forward_v1.py",
    "sue_quarterly_v1": "record_sue_quarterly_forward_v1.py",
    "residual_tie_agnostic_companion_v1": "record_residual_tie_agnostic_companion_forward_v1.py",
}
# This recorder appends its decision unconditionally, so it may only be called once per Friday.
NOT_IDEMPOTENT = {"residual_tie_agnostic_companion_v1"}


class CycleError(RuntimeError):
    pass


def latest_decision_friday(now: datetime):
    spec = importlib.util.spec_from_file_location("guarded", ROOT / "scripts/run_guarded_weekly_forward_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.latest_closed_decision_week(now)


def log_dates(clock: str, name: str, field: str) -> set[str]:
    path = ROOT / f"evidence/forward_{clock}/{name}"
    if not path.exists():
        return set()
    return {str(json.loads(line)[field]) for line in path.read_text().splitlines() if line.strip()}


def panel_last_week(key: str) -> str:
    manifest = json.loads(PANELS[key].read_text())
    return str(manifest.get("new_last_week") or manifest.get("last_week"))


class Runner:
    def __init__(self, friday: str, dry_run: bool):
        self.friday, self.dry_run, self.steps = friday, dry_run, []

    def run(self, label: str, command: list[str], ok_codes: tuple[int, ...] = (0,), ok_text: str = "") -> str:
        if self.dry_run:
            self.steps.append({"step": label, "command": command, "status": "dry_run"})
            print(f"[dry-run] {label}: {' '.join(command)}")
            return ""
        print(f"==> {label}", flush=True)
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        output = (done.stdout or "") + (done.stderr or "")
        passed = done.returncode in ok_codes or (ok_text and ok_text in output)
        self.steps.append({"step": label, "command": command, "returncode": done.returncode,
                           "status": "ok" if passed else "failed", "tail": output.strip().splitlines()[-12:]})
        if not passed:
            raise CycleError(f"{label} failed (exit {done.returncode}):\n" + "\n".join(output.strip().splitlines()[-12:]))
        return output


def notify(title: str, message: str) -> None:
    script = f'display notification {json.dumps(message[:220])} with title {json.dumps(title)}'
    subprocess.run(["/usr/bin/osascript", "-e", script], check=False, capture_output=True)


def pending(friday: str) -> dict[str, list[str]]:
    prior = str((datetime.fromisoformat(friday) - timedelta(days=7)).date())
    todo = {"etf": [c for c in ETF_CLOCKS if friday not in log_dates(c, "decisions.jsonl", "decision_date")], "stock": []}
    for clock in STOCK_RECORDERS:
        decided = friday in log_dates(clock, "decisions.jsonl", "decision_date")
        realization_due = prior in log_dates(clock, "decisions.jsonl", "decision_date")
        realized = friday in log_dates(clock, "observations.jsonl", "realization_date")
        if not decided or (realization_due and not realized and clock not in NOT_IDEMPOTENT):
            todo["stock"].append(clock)
    return todo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    parser.add_argument("--commit", action="store_true", help="commit the recorded week to git")
    parser.add_argument("--push", action="store_true", help="also push HEAD to origin/main (redeploys the dashboard)")
    parser.add_argument("--notify", action="store_true", help="macOS notification on success and failure")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    friday = str(latest_decision_friday(now))
    todo = pending(friday)
    print(f"decision Friday {friday}; window closes {friday} + 7d 21:00 UTC; "
          f"pending ETF {todo['etf'] or 'none'}, stock {todo['stock'] or 'none'}")
    if not todo["etf"] and not todo["stock"]:
        print("every clock already carries this week; nothing to do")
        return 0

    runner = Runner(friday, args.dry_run)
    RUNS.mkdir(parents=True, exist_ok=True)
    record = {"decision_friday": friday, "started_at_utc": now.isoformat(), "pending": todo, "live_trading_enabled": False}
    try:
        if todo["etf"]:
            runner.run("start the Podman sandbox", [PODMAN, "machine", "start", PODMAN_MACHINE], ok_text="already running")
            if "covariance_minimum_variance_v1" in todo["etf"]:
                runner.run("guarded weekly cycle (minimum variance)", [PYTHON, "scripts/run_guarded_weekly_forward_cycle.py"])
            runner.run("frozen-book recorders",
                       [PYTHON, "scripts/record_frozen_book_forward_evidence_v1.py",
                        *[x for p in FROZEN_BOOK_PROTOCOLS for x in ("--protocol", p)]])

        if todo["stock"]:
            runner.run("extend the narrow weekly panel", [PYTHON, "scripts/extend_weekly_price_panel_v2.py"])
            runner.run("re-acquire full-history prices", [PYTHON, "scripts/acquire_broad_full_history_prices_v1.py"])
            runner.run("rebuild the broad full-history panel", [PYTHON, "scripts/build_broad_full_history_panel_v1.py"])
            runner.run("corporate-action clean the full-history panel",
                       [PYTHON, "scripts/build_corporate_action_clean_prices_v1.py",
                        "--prices", "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz",
                        "--output", "data/clean_full_history_prices_v1"])
            if not args.dry_run:
                for key in PANELS:
                    if panel_last_week(key) != friday:
                        raise CycleError(f"the {key} panel ends {panel_last_week(key)}, not {friday}; "
                                         "the data source has not published the week yet -- retry later")
            prior = str((datetime.fromisoformat(friday) - timedelta(days=7)).date())
            for clock in todo["stock"]:
                command = [PYTHON, f"scripts/{STOCK_RECORDERS[clock]}", "--decision-date", friday]
                if prior in log_dates(clock, "decisions.jsonl", "decision_date"):
                    command.append("--realize")
                runner.run(f"record {clock}", command)

        runner.run("mark the dashboard books", [PYTHON, "scripts/mark_last_books_to_market_v1.py"])
        runner.run("benchmark and energy attribution", [PYTHON, "scripts/build_held_book_attribution_v1.py"])
        runner.run("what-if replay", [PYTHON, "scripts/build_paper_replay_v1.py"])
        runner.run("forward tracker payload", [PYTHON, "scripts/build_forward_tracker_payload_v1.py"])
        runner.run("research status payload", [PYTHON, "scripts/build_research_status_payload_v1.py"])

        if not args.dry_run:
            behind = [c for c in [*ETF_CLOCKS, *STOCK_RECORDERS] if friday not in log_dates(c, "decisions.jsonl", "decision_date")]
            if behind:
                raise CycleError(f"clocks still missing {friday} after the run: {behind}")
            verify = ("import sys; sys.path.insert(0, '.'); from pathlib import Path; "
                      "from src.systematic_trader.forward_evidence import read_and_verify_log as v\n"
                      "for d in Path('evidence').glob('forward_*/decisions.jsonl'):\n"
                      "    v(d, date_field='decision_date', first_eligible_date='2000-01-07')\n"
                      "    o = d.with_name('observations.jsonl')\n"
                      "    o.exists() and o.stat().st_size and v(o, date_field='realization_date', first_eligible_date='2000-01-07')\n"
                      "print('hash chains verify')")
            runner.run("verify every hash chain", [PYTHON, "-c", verify])

            if args.commit:
                runner.run("git add", ["/usr/bin/git", "-C", str(REPO), "add", "2.0/evidence", "2.0/data", "2.0/dashboard/public",
                                       "2.0/research_registry"])
                runner.run("git commit", ["/usr/bin/git", "-C", str(REPO), "commit", "-q", "-m",
                                          f"Forward week {friday}: all clocks recorded (automated)\n\n"
                                          "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"],
                           ok_codes=(0, 1))
                if args.push:
                    runner.run("git push", ["/usr/bin/git", "-C", str(REPO), "push", "-q", "origin", "HEAD:main"])
        record["status"] = "complete"
        message = f"Dry run only; nothing recorded for {friday}." if args.dry_run else f"All clocks recorded for {friday}."
    except CycleError as error:
        record["status"], record["error"] = "failed", str(error)
        message = f"FAILED for {friday}: {str(error).splitlines()[0]}"
    record["steps"], record["finished_at_utc"] = runner.steps, datetime.now(timezone.utc).isoformat()
    if not args.dry_run:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (RUNS / f"{friday}-{stamp}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(message)
    if args.notify:
        notify("Portfolio Optimizer forward clock", message)
    return 0 if record["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
