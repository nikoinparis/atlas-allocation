"""Decile-ladder replication of the Step 296 skill screen on WorldQuant BRAIN data.

This does NOT search for a strategy. It runs the one measurement BRAIN does not report —
decile monotonicity — on their point-in-time panel, to see whether the null established in
Steps 296/298/299/300 replicates on data this project does not own.

Read `docs/WORLDQUANT_BRAIN_EVALUATION_V1.md` before running. In particular:

  * Phase 0 (field-id confirmation and the density audit) comes first. The field ids below
    are the commonly-cited ones and are UNVERIFIED. Run --audit-fields and fix them.
  * A BRAIN Sharpe is not evidence here. Monotonicity is. Every signal measured in this
    project sits within +/-0.17 of zero; the declared bar is monotonicity above 0.5 with
    interpretable deciles.
  * BRAIN cannot count its own multiple testing. Nothing is promoted out of this.

UNVALIDATED AGAINST THE LIVE API: written in an environment where api.worldquantbrain.com
is egress-blocked, so no call here has ever executed. Treat the first run as a debugging
run and check the raw responses.

Credentials come from a JSON file (default ~/.worldquant_brain.json):

    {"email": "...", "password": "..."}
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

API = "https://api.worldquantbrain.com"

# UNVERIFIED -- confirm with --audit-fields before trusting any result built on these.
FIELDS = {
    "sales": "sales",
    "cashflow_op": "cashflow_op",
    "capex": "capex",
    "net_income": "net_income",
    "assets": "assets",
    "equity": "equity",
    "liabilities": "liabilities",
    "debt": "debt",
    "cash": "cash",
}

# Direct translations of build_dashboard_signals_out_of_sample_v1.py::SIGNALS.
SIGNALS = {
    "cash_conversion": (
        "ocf_margin = {cashflow_op} / {sales};"
        "fcf_margin = ({cashflow_op} - {capex}) / {sales};"
        "spread = ocf_margin - ({net_income} / {sales});"
        "(group_rank(ocf_margin, {g}) + group_rank(fcf_margin, {g})"
        " + group_rank(spread, {g})) / 3"
    ),
    "balance_sheet_quality": (
        "(group_rank({cash} / {assets}, {g}) + group_rank({equity} / {assets}, {g})"
        " - group_rank({debt} / {assets}, {g})"
        " - group_rank({liabilities} / {assets}, {g})) / 4"
    ),
    "growth": (
        "g_rev = ts_delta({sales}, 250) / abs(ts_delay({sales}, 250));"
        "g_ni = ts_delta({net_income}, 250) / abs(ts_delay({net_income}, 250));"
        "g_ocf = ts_delta({cashflow_op}, 250) / abs(ts_delay({cashflow_op}, 250));"
        "(group_rank(g_rev, {g}) + group_rank(g_ni, {g}) + group_rank(g_ocf, {g})) / 3"
    ),
    # Negative control: raw size should be flat once grouped. If this ladder orders itself,
    # the harness is measuring something other than the signal and nothing else is readable.
    "control_size": "group_rank({assets}, {g})",
}

BASE_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,              # never 0 -- delay 0 is where the same-bar lookahead class lives
    "decay": 0,
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}


def body(signal: str, group: str) -> str:
    return SIGNALS[signal].format(g=group, **FIELDS)


def decile_alpha(signal: str, group: str, decile: int) -> str:
    """Long-only, equal-weight on one decile. Run with neutralization NONE.

    All ten deciles carry the same long-only market exposure, so comparing across them is
    beta-neutral in the sense cross_sectional_skill_registry_v1 defines.
    """
    lo, hi = (decile - 1) / 10.0, decile / 10.0
    return f"sig = {body(signal, group)};r = rank(sig);if_else(r > {lo} && r <= {hi}, 1, 0)"


def spread_alpha(signal: str, group: str) -> str:
    """Top decile minus bottom decile, as a dollar-neutral book."""
    return (f"sig = {body(signal, group)};r = rank(sig);"
            "if_else(r > 0.9, 1, if_else(r < 0.1, -1, 0))")


def login(credentials: Path) -> requests.Session:
    creds = json.loads(credentials.read_text())
    session = requests.Session()
    session.auth = HTTPBasicAuth(creds["email"], creds["password"])
    response = session.post(f"{API}/authentication")
    if response.status_code != 201:
        raise SystemExit(f"authentication failed: {response.status_code} {response.text[:400]}")
    return session


def simulate(session: requests.Session, expression: str, neutralization: str,
             timeout: int = 900) -> dict:
    settings = dict(BASE_SETTINGS, neutralization=neutralization)
    payload = {"type": "REGULAR", "settings": settings, "regular": expression}
    response = session.post(f"{API}/simulations", json=payload)
    if response.status_code != 201:
        return {"error": f"{response.status_code} {response.text[:400]}"}
    location = response.headers.get("Location", "").rstrip("/")
    if not location:
        return {"error": "no Location header on 201"}

    deadline = time.time() + timeout
    while time.time() < deadline:
        poll = session.get(location)
        if poll.status_code != 200:
            time.sleep(5.0)
            continue
        state = poll.json()
        status = state.get("status")
        if status == "COMPLETE":
            alpha_id = state.get("alpha")
            if not alpha_id:
                return {"error": f"complete without alpha id: {state}"}
            alpha = session.get(f"{API}/alphas/{alpha_id}")
            if alpha.status_code != 200:
                return {"error": f"alpha fetch {alpha.status_code}"}
            return {"alpha_id": alpha_id, "alpha": alpha.json()}
        if status in {"FAILED", "ERROR"}:
            return {"error": f"{status}: {state.get('message', state)}"}
        time.sleep(float(poll.headers.get("Retry-After", 5.0)))
    return {"error": "timed out"}


def statistic(alpha: dict, name: str) -> float:
    return float((alpha.get("is") or {}).get(name, float("nan")))


def monotonicity(returns_by_decile: dict[int, float]) -> float:
    """Spearman correlation between decile index and decile mean return.

    The measure that decides. It reads the shape of the relationship rather than its
    significance, so it does not depend on having many independent windows -- which matters
    because quarterly fundamentals on a daily grid give ~52 independent decisions, not 3,250.
    """
    present = sorted(d for d in returns_by_decile if returns_by_decile[d] == returns_by_decile[d])
    if len(present) < 8:
        return float("nan")
    values = [returns_by_decile[d] for d in present]
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for position, index in enumerate(order):
        ranks[index] = float(position + 1)
    return statistics.correlation([float(d) for d in present], ranks)


def audit_fields(session: requests.Session, dataset: str) -> int:
    response = session.get(f"{API}/data-fields",
                           params={"dataset.id": dataset, "region": BASE_SETTINGS["region"],
                                   "universe": BASE_SETTINGS["universe"],
                                   "delay": BASE_SETTINGS["delay"], "limit": 200})
    if response.status_code != 200:
        print(f"data-fields failed: {response.status_code} {response.text[:400]}")
        return 1
    print(f"{'id':32} {'coverage':>9}  description")
    for field in response.json().get("results", []):
        print(f"{field.get('id', ''):32} {str(field.get('coverage', '')):>9}  "
              f"{str(field.get('description', ''))[:70]}")
    print("\nDENSITY GUARD: a field below 50% coverage cannot be read on deciles at all.")
    print("Step 298 nearly reported a discovery on a signal that was 93.3% zeros.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credentials", type=Path,
                        default=Path.home() / ".worldquant_brain.json")
    parser.add_argument("--signals", nargs="*", default=list(SIGNALS))
    parser.add_argument("--group", default="sector",
                        help="BRAIN grouping; our panel uses a hand-built SIC major-group map, "
                             "so this is a construction difference, not an equivalence")
    parser.add_argument("--audit-fields", metavar="DATASET_ID",
                        help="Phase 0: list a dataset's fields and coverage, then exit")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "evidence/worldquant_brain_decile_ladder_v1")
    args = parser.parse_args()

    session = login(args.credentials)

    if args.audit_fields:
        return audit_fields(session, args.audit_fields)

    args.output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}

    for signal in args.signals:
        if signal not in SIGNALS:
            print(f"unknown signal {signal!r}", file=sys.stderr)
            return 2
        print(f"\n=== {signal} ===", flush=True)
        ladder: dict[int, float] = {}
        records: dict[str, dict] = {}

        for decile in range(1, 11):
            result = simulate(session, decile_alpha(signal, args.group, decile), "NONE")
            if "error" in result:
                print(f"  decile {decile:2d}: {result['error']}", flush=True)
                ladder[decile] = float("nan")
                continue
            returns = statistic(result["alpha"], "returns")
            ladder[decile] = returns
            records[f"decile_{decile}"] = result["alpha"].get("is", {})
            print(f"  decile {decile:2d}: returns {returns:+.4f}", flush=True)

        spread = simulate(session, spread_alpha(signal, args.group), "NONE")
        production = simulate(session, body(signal, args.group), "SUBINDUSTRY")
        for label, result in (("spread", spread), ("production", production)):
            if "error" in result:
                print(f"  {label}: {result['error']}", flush=True)
            else:
                records[label] = result["alpha"].get("is", {})
                print(f"  {label}: sharpe {statistic(result['alpha'], 'sharpe'):+.3f} "
                      f"returns {statistic(result['alpha'], 'returns'):+.4f} "
                      f"turnover {statistic(result['alpha'], 'turnover'):.4f}", flush=True)

        mono = monotonicity(ladder)
        top, bottom = ladder.get(10, float("nan")), ladder.get(1, float("nan"))
        summary[signal] = {"monotonicity": mono, "decile_returns": ladder,
                           "top_minus_bottom": top - bottom, "checks": records}
        print(f"  MONOTONICITY {mono:+.3f}   top-minus-bottom {top - bottom:+.4f}", flush=True)

    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))

    print("\n--- reading, declared before the run ---")
    print("Bar: monotonicity above 0.5 with interpretable deciles. Every signal measured in")
    print("this project sits within +/-0.17 of zero. Below that bar replicates the Step 296")
    print("null on independent data, which is the expected and the valuable outcome.")
    print("A positive IC alongside a negative decile spread is noise measured twice, not a")
    print("lead. Nothing is promoted out of this run regardless of what it shows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
