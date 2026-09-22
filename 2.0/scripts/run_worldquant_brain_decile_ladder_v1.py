"""Decile-ladder replication of the Step 296 skill screen on WorldQuant BRAIN data.

This does NOT search for a strategy. It runs the one measurement BRAIN does not report —
decile monotonicity — on their point-in-time panel, to see whether the null established in
Steps 296/298/299/300 replicates on data this project does not own.

Read `docs/WORLDQUANT_BRAIN_EVALUATION_V1.md` before running. In particular:

  * Phase 0 comes first and is one command: `--phase0`. It downloads every relevant
    dataset's field dictionary to CSV and resolves the nine field ids our signals need.
    The ids hard-coded below are UNVERIFIED -- `net_income` is already known WRONG,
    rejected by the simulator on 2026-09-22 as an unknown variable.
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
import csv
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
    # RESOLVED 2026-09-22 (Phase 0, fundamental6.csv). `net_income` does not exist; the
    # field is `income`, whose description is exactly "Net Income" -- and it is the ONLY
    # field in the dataset with that exact description. MATRIX, coverage 0.5, 15,876 alphas,
    # on the same bare-id convention as sales/assets/equity/debt/cash/capex/cashflow_op.
    #
    # This is a RESOLUTION, not a substitution: `income` IS net income, so cash_conversion
    # still measures cash conversion. `ebit`/`ebitda` were deliberately NOT used, because
    # those would change what the signal measures while keeping its name.
    #
    # Caveat carried forward, same class as the open `debt`/`liabilities` question: this is
    # Compustat NI, and our SEC panel sums the `NetIncomeLoss` tag. Close, not proven equal.
    "net_income": "income",
    "assets": "assets",
    "equity": "equity",
    "liabilities": "liabilities",
    "debt": "debt",
    "cash": "cash",
}

# Direct translations of build_dashboard_signals_out_of_sample_v1.py::SIGNALS.
#
# Written as SINGLE inlined expressions on purpose. FastExpr's multi-statement /
# variable-assignment form is not reliably documented at every account tier, and a parser
# rejection costs a simulation slot. Verbose beats clever here.
#
# Quarterly (not trailing-four-quarter) fields are fine for all three signals: margins are
# ratios so quarterly/quarterly is a valid margin, YoY growth over ~250 trading days
# compares a quarter against the same quarter a year earlier, and balance-sheet ratios are
# stock/stock. Do NOT try to build TTM with ts_sum -- these fields are step functions on a
# daily grid, so ts_sum(x, 250) sums the same forward-filled value ~250 times.
SIGNALS = {
    "cash_conversion": (
        "(group_rank({cashflow_op} / {sales}, {g})"
        " + group_rank(({cashflow_op} - {capex}) / {sales}, {g})"
        " + group_rank({cashflow_op} / {sales} - {net_income} / {sales}, {g})) / 3"
    ),
    "balance_sheet_quality": (
        "(group_rank({cash} / {assets}, {g}) + group_rank({equity} / {assets}, {g})"
        " - group_rank({debt} / {assets}, {g})"
        " - group_rank({liabilities} / {assets}, {g})) / 4"
    ),
    "growth": (
        "(group_rank(ts_delta({sales}, 250) / abs(ts_delay({sales}, 250)), {g})"
        " + group_rank(ts_delta({net_income}, 250) / abs(ts_delay({net_income}, 250)), {g})"
        " + group_rank(ts_delta({cashflow_op}, 250) / abs(ts_delay({cashflow_op}, 250)), {g}))"
        " / 3"
    ),
    # Negative control: raw size, flat once grouped. If this ladder orders itself, the
    # harness is measuring something other than the signal and nothing else is readable.
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

    Built as the difference of two step functions rather than a compound condition:
    (rank > lo) - (rank > hi) is exactly the indicator for the half-open band, and uses only
    a single `>` comparison per term. FastExpr's boolean operators are function-style
    (`and`, `less`, `greater`) rather than `&&`, so compound conditions are avoided entirely.

    The lower edge for decile 1 is -1 rather than 0 so that both terms propagate NaN
    identically; rank() can return exactly 0 for the minimum name, which `> 0` would drop.

    All ten deciles carry the same long-only market exposure, so comparing across them is
    beta-neutral in the sense cross_sectional_skill_registry_v1 defines.
    """
    lo = -1.0 if decile == 1 else (decile - 1) / 10.0
    hi = decile / 10.0
    sig = body(signal, group)
    return (f"if_else(rank({sig}) > {lo}, 1, 0)"
            f" - if_else(rank({sig}) > {hi}, 1, 0)")


def spread_alpha(signal: str, group: str) -> str:
    """Top decile minus bottom decile, as a dollar-neutral book."""
    sig = body(signal, group)
    return (f"if_else(rank({sig}) > 0.9, 1, 0)"
            f" - if_else(rank({sig}) > 0.1, 0, 1)")


def print_expressions(signals: list[str], group: str) -> int:
    """Dump every expression for copy-paste into the web simulator.

    Offline. The web UI is the sane way to do the first pass -- you see parse errors
    immediately instead of spending a simulation slot to discover one.
    """
    for signal in signals:
        print(f"\n{'=' * 78}\n{signal}\n{'=' * 78}")
        print("\n-- production form (neutralization SUBINDUSTRY) --")
        print(body(signal, group))
        print("\n-- decile ladder (neutralization NONE, one simulation each) --")
        for decile in range(1, 11):
            print(f"\n[decile {decile}]")
            print(decile_alpha(signal, group, decile))
        print("\n-- top-minus-bottom spread (neutralization NONE) --")
        print(spread_alpha(signal, group))
    print("\nField ids above are UNVERIFIED. Confirm them on the Data tab first.")
    return 0


def verdict(shape: dict) -> str:
    """The declared reading, applied to a ladder. Declared before any number was seen.

    NaN is not "flat" -- it means the ladder was degenerate (every decile identical, or too
    few present to score) and carries no information either way. Saying so is the honest
    report; the previous code would have called a dead-flat ladder a perfect ordering.
    """
    mono, middle = shape["monotonicity"], shape["monotonicity_middle_8"]
    if mono != mono:
        return "DEGENERATE -- ladder carries no ordering information, not readable"
    if mono <= -0.5:
        # An inverted ladder is not flat and must not be reported as such. It refutes the
        # declared sign. It is NOT re-read as a discovery with the sign flipped: Step 286
        # recorded Form 4 as "refuted on sign, rather than flipped" and Step 282 refused to
        # rescue a -28% book by reversing it. Post-hoc flipping doubles the search space for
        # free and turns every refutation into a discovery.
        return ("INVERTED -- refutes the declared sign. NOT flipped; a sign-flipped variant "
                "is a new hypothesis needing its own pre-registration and window.")
    if mono <= 0.5:
        return "flat -- replicates the null"
    # Past here the full ladder is positively ordered, so the middle eight must order in the
    # SAME direction. A positive ladder sitting on a negative middle is incoherent, not clean.
    if middle != middle or middle <= 0.5:
        return "CONCENTRATION in the extremes, not an ordering -- middle eight do not order"
    return "ORDERS ITS DECILES -- clears the declared bar"


def report(signal: str, shape: dict) -> None:
    print(f"{signal:24} monotonicity {shape['monotonicity']:+.3f}  "
          f"middle-8 {shape['monotonicity_middle_8']:+.3f}  "
          f"top-minus-bottom {shape['top_minus_bottom']:+.4f}  "
          f"dispersion {shape['decile_dispersion']:.4f}  "
          f"distinct {shape['distinct_values']}/10\n"
          f"{'':24} {verdict(shape)}")


def score_manual(path: Path) -> int:
    """Score decile returns typed in from the web UI.

    Input JSON: {"<signal>": {"1": 0.0123, "2": -0.004, ... "10": 0.031}, ...}
    Returns as decimals (0.0123 = 1.23%), read off each decile alpha's `returns` stat.

    Note this path is the one most exposed to tie-induced artefacts, because the values are
    whatever the web UI displayed -- rounded. See _midranks.
    """
    raw = json.loads(path.read_text())
    summary = {}
    for signal, deciles in raw.items():
        ladder = {int(k): float(v) for k, v in deciles.items()}
        shape = dict(ladder_shape(ladder), decile_returns=ladder)
        summary[signal] = shape
        report(signal, shape)
    print("\nBar declared in advance: monotonicity above 0.5 WITH interpretable deciles.")
    print("Every signal measured in this project sits within +/-0.17 of zero.")
    print("A positive spread with a flat ladder is a concentration effect, not skill --")
    print("nine tied deciles plus one large top decile scores about +0.52 on the headline")
    print("number alone, which is why middle-8 is reported beside it and both must clear.")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def login(credentials: Path) -> requests.Session:
    if not credentials.exists():
        raise SystemExit(
            f"No credentials at {credentials}.\n"
            "On macOS/Linux run:  bash 2.0/scripts/setup_worldquant_brain.sh\n"
            "On Windows run:      powershell -ExecutionPolicy Bypass -File "
            "2.0\\scripts\\setup_worldquant_brain.ps1\n"
            "Both prompt for the password without echoing it.")
    creds = json.loads(credentials.read_text())
    session = requests.Session()
    session.auth = HTTPBasicAuth(creds["email"], creds["password"])
    response = session.post(f"{API}/authentication")
    if response.status_code == 201:
        return session
    if response.status_code == 401 and "persona" in response.text.lower():
        raise SystemExit(
            "BRAIN wants biometric/persona verification before it will issue an API session.\n"
            "Complete it once in the browser at platform.worldquantbrain.com, then re-run.")
    raise SystemExit(f"authentication failed: {response.status_code} {response.text[:400]}")


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


def _midranks(values: list[float]) -> list[float]:
    """Average ranks, so tied values share a rank instead of being ordered by position.

    This is not a refinement. Ordinal ranking of ties is what made a PERFECTLY FLAT ladder
    report monotonicity +1.000 -- `sorted` is stable, so equal returns were handed ranks in
    ascending decile order and Spearman read a flawless staircase out of nothing. BRAIN
    displays returns to two decimals of a percent, and at that precision a flat ladder shows
    four to six exact ties out of ten, so this fired on real numbers, and hardest on the
    --score-manual path where the values are typed in from the web UI exactly as displayed.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        stop = position
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[position]]:
            stop += 1
        shared = (position + stop) / 2.0 + 1.0
        for index in order[position:stop + 1]:
            ranks[index] = shared
        position = stop + 1
    return ranks


def monotonicity(returns_by_decile: dict[int, float]) -> float:
    """Spearman correlation between decile index and decile mean return.

    The measure that decides. It reads the shape of the relationship rather than its
    significance, so it does not depend on having many independent windows -- which matters
    because quarterly fundamentals on a daily grid give ~52 independent decisions, not 3,250.

    Returns NaN when every decile carries the same return: Spearman is undefined at zero
    variance, and the honest report for a dead-flat ladder is "no ordering", never +1.
    """
    present = sorted(d for d in returns_by_decile if returns_by_decile[d] == returns_by_decile[d])
    if len(present) < 8:
        return float("nan")
    values = [returns_by_decile[d] for d in present]
    if len(set(values)) == 1:
        return float("nan")
    ranks = _midranks(values)
    if len(set(ranks)) == 1:
        return float("nan")
    return statistics.correlation([float(d) for d in present], ranks)


def ladder_shape(returns_by_decile: dict[int, float]) -> dict:
    """Separate a genuine ordering from a concentration effect in the extremes.

    CLAUDE.md records the shape six times over: a large top-minus-bottom spread sitting on
    an unordered middle is noise measured twice, not skill. Monotonicity over the full ten
    cannot tell those apart on its own -- nine tied deciles plus one large top decile still
    scores about +0.58 with correct midranks, which clears the declared 0.5 bar on pure
    concentration. So the middle eight are scored separately, and the declared reading is
    "above 0.5 WITH interpretable deciles", not the headline number alone.
    """
    present = {d: v for d, v in returns_by_decile.items() if v == v}
    values = list(present.values())
    middle = {d: v for d, v in present.items() if 2 <= d <= 9}
    top, bottom = present.get(10, float("nan")), present.get(1, float("nan"))
    spread = top - bottom
    inner = (present.get(9, float("nan")) - present.get(2, float("nan")))
    return {
        "monotonicity": monotonicity(returns_by_decile),
        "monotonicity_middle_8": monotonicity(middle) if len(middle) >= 8 else float("nan"),
        "top_minus_bottom": spread,
        "inner_spread_d9_minus_d2": inner,
        "distinct_values": len(set(values)),
        "decile_dispersion": statistics.pstdev(values) if len(values) > 1 else float("nan"),
        "extremes_share_of_spread": (
            1.0 - inner / spread if spread == spread and inner == inner and spread != 0
            else float("nan")),
    }


CONCEPTS = {
    "sales":       ("sales", "revenue", "net sales", "total revenue"),
    "cashflow_op": ("operating activities", "cash flow from operations", "cashflow_op"),
    "capex":       ("capital expenditure", "capex"),
    # Deliberately wide. `net_income` was rejected by the simulator as an unknown variable
    # on 2026-09-22 and is the single blocker on two of three signals, so this errs toward
    # false positives -- a human picks from the hits, and missing the field costs a session.
    "net_income":  ("net income", "income - net", "net profit", "earnings",
                    "income before extraordinary", "income (loss)", "netincome",
                    "profit after tax", "bottom line"),
    "assets":      ("assets - total", "total assets"),
    "equity":      ("stockholders equity", "shareholders equity", "common equity", "equity"),
    "liabilities": ("liabilities - total", "total liabilities", "liabilities"),
    "cash":        ("cash", "cash and short-term"),
    "debt":        ("debt", "long-term debt", "total debt"),
}


def phase0(session: requests.Session, root: Path) -> int:
    """One command: dump every fundamental dataset's fields and resolve our nine concepts.

    Exists because 45 pages of web UI is not a reference, and because one unknown field id
    (`net_income`, rejected 2026-09-22) already cost a round of simulations.
    """
    out = root / "data/worldquant_brain_fields"
    out.mkdir(parents=True, exist_ok=True)
    params = {"region": BASE_SETTINGS["region"], "universe": BASE_SETTINGS["universe"],
              "delay": BASE_SETTINGS["delay"], "instrumentType": "EQUITY"}

    datasets = _paged(session, f"{API}/data-sets", params)
    with (out / "_datasets.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name", "category", "fieldCount", "alphaCount"])
        for row in datasets:
            writer.writerow([row.get("id", ""), row.get("name", ""),
                             (row.get("category") or {}).get("name", ""),
                             row.get("fieldCount", ""), row.get("alphaCount", "")])
    print(f"{len(datasets)} datasets -> {out / '_datasets.csv'}\n")

    wanted = [d for d in datasets
              if any(k in f"{d.get('id','')} {d.get('name','')}".lower()
                     for k in ("fundamental", "company", "analyst", "model"))]
    if not wanted:
        wanted = datasets[:5]

    fields: list[tuple[str, dict]] = []
    skipped: list[str] = []
    for dataset in wanted:
        did = dataset.get("id", "")
        try:
            rows = _paged(session, f"{API}/data-fields", dict(params, **{"dataset.id": did}))
        except SystemExit as error:                      # one bad dataset must not stop Phase 0
            print(f"  {did}: SKIPPED ({error})")
            skipped.append(did)
            continue
        with (out / f"{did}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "description", "type", "coverage", "alphaCount"])
            for row in rows:
                writer.writerow([row.get("id", ""), row.get("description", ""),
                                 row.get("type", ""), row.get("coverage", ""),
                                 row.get("alphaCount", "")])
        fields.extend((did, row) for row in rows)
        print(f"  {did}: {len(rows)} fields -> {out / f'{did}.csv'}")

    print("\n" + "=" * 78)
    print("PASTE EVERYTHING BELOW THIS LINE BACK INTO THE CONVERSATION")
    print("=" * 78)
    for concept, needles in CONCEPTS.items():
        print(f"\n--- {concept} ---")
        hits = []
        for dataset_id, row in fields:
            blob = f"{row.get('id','')} {row.get('description','')}".lower()
            if any(n in blob for n in needles):
                hits.append((dataset_id, row))
        if not hits:
            print("  NO MATCH -- this concept may not exist on the platform")
        for dataset_id, row in hits[:8]:
            print(f"  {row.get('id',''):26} cov={str(row.get('coverage','')):>7}  "
                  f"[{dataset_id}]  {str(row.get('description',''))[:52]}")
    print("\n" + "=" * 78)
    print("DENSITY GUARD: a field below 50% coverage cannot be read on deciles at all.")
    print("=" * 78)
    if skipped:
        print("\n" + "!" * 78)
        print(f"INCOMPLETE: {len(skipped)} dataset(s) failed and were skipped: "
              f"{', '.join(skipped)}")
        print("A 'NO MATCH' above is NOT evidence the concept is absent while this is set.")
        print("Re-run --phase0, or sweep with --find-field all <text>, before concluding.")
        print("!" * 78)
    return 0


def _get(session: requests.Session, url: str, params: dict,
         attempts: int = 6) -> requests.Response:
    """GET with backoff on 429.

    BRAIN rate-limits at 50 requests per minute (`ratelimit-limit: 50` on every response,
    confirmed live on 2026-09-22, and a second unauthenticated call one second later came
    back 429). Phase 0 walks several datasets at 50 rows a page, so it WILL hit this. Without
    a retry the walk aborts mid-dictionary, and in phase0 the failure is caught per-dataset
    and printed as "skipped" -- which yields a field dictionary that looks complete and is
    not. That is precisely how a field gets declared non-existent when it was merely on the
    far side of a rate limit.
    """
    for attempt in range(attempts):
        response = session.get(url, params=params)
        if response.status_code != 429:
            return response
        pause = float(response.headers.get("Retry-After")
                      or response.headers.get("ratelimit-reset") or 15.0)
        pause = min(max(pause, 1.0), 90.0) * (1.0 + 0.5 * attempt)
        print(f"    rate-limited, sleeping {pause:.0f}s "
              f"(attempt {attempt + 1}/{attempts})", flush=True)
        time.sleep(pause)
    return response


def _paged(session: requests.Session, url: str, params: dict) -> list[dict]:
    """Walk an offset-paginated BRAIN collection to exhaustion."""
    rows, offset = [], 0
    while True:
        response = _get(session, url, dict(params, limit=50, offset=offset))
        if response.status_code != 200:
            raise SystemExit(f"{url} -> {response.status_code} {response.text[:400]}")
        payload = response.json()
        batch = payload.get("results", [])
        rows.extend(batch)
        offset += len(batch)
        if not batch:
            return rows
        # Only trust `count` when the response actually carries one. The previous form
        # defaulted it to 0, so a response without `count` returned after a single page of
        # 50 and looked like a complete dictionary -- which is how a field gets declared
        # non-existent when it was merely on page two.
        total = payload.get("count")
        if isinstance(total, int) and offset >= total:
            return rows


def list_datasets(session: requests.Session) -> int:
    params = {"region": BASE_SETTINGS["region"], "universe": BASE_SETTINGS["universe"],
              "delay": BASE_SETTINGS["delay"], "instrumentType": "EQUITY"}
    for row in _paged(session, f"{API}/data-sets", params):
        print(f"{row.get('id', ''):28} {str(row.get('name', ''))[:70]}")
    return 0


def dump_fields(session: requests.Session, dataset: str, output: Path) -> int:
    """Download a dataset's whole field dictionary to CSV.

    45 pages of web UI is not a reference you can work from. This is, and committing it
    means the field ids stop being the thing that blocks every future session.
    """
    params = {"dataset.id": dataset, "region": BASE_SETTINGS["region"],
              "universe": BASE_SETTINGS["universe"], "delay": BASE_SETTINGS["delay"],
              "instrumentType": "EQUITY"}
    rows = _paged(session, f"{API}/data-fields", params)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "description", "type", "coverage", "userCount", "alphaCount"])
        for row in rows:
            writer.writerow([row.get("id", ""), row.get("description", ""),
                             row.get("type", ""), row.get("coverage", ""),
                             row.get("userCount", ""), row.get("alphaCount", "")])
    print(f"{len(rows)} fields -> {output}")
    thin = [r.get("id") for r in rows
            if isinstance(r.get("coverage"), (int, float)) and r["coverage"] < 0.5]
    if thin:
        print(f"DENSITY GUARD: {len(thin)} field(s) below 50% coverage, unreadable on "
              f"deciles: {', '.join(map(str, thin[:12]))}")
    return 0


def find_field(session: requests.Session, dataset: str, needle: str) -> int:
    """Search one dataset's fields, or every dataset when given the id `all`.

    The `all` sweep exists because Phase 0's CSV dump is restricted to datasets whose name
    looks fundamental, and a field that lives outside that filter would read as "does not
    exist on the platform" when it merely lives somewhere unexpected.
    """
    base = {"region": BASE_SETTINGS["region"], "universe": BASE_SETTINGS["universe"],
            "delay": BASE_SETTINGS["delay"], "instrumentType": "EQUITY"}
    if dataset == "all":
        targets = [d.get("id", "") for d in _paged(session, f"{API}/data-sets", base)]
        print(f"sweeping {len(targets)} datasets for {needle!r}\n")
    else:
        targets = [dataset]

    needle = needle.lower()
    hits = 0
    for target in targets:
        try:
            rows = _paged(session, f"{API}/data-fields", dict(base, **{"dataset.id": target}))
        except SystemExit as error:               # one bad dataset must not stop the sweep
            print(f"  {target}: skipped ({error})")
            continue
        for row in rows:
            blob = f"{row.get('id', '')} {row.get('description', '')}".lower()
            if needle in blob:
                hits += 1
                print(f"{row.get('id', ''):28} cov={str(row.get('coverage', '')):>6}  "
                      f"[{target}]  {str(row.get('description', ''))[:56]}")
    if not hits:
        print(f"no field matches {needle!r}. If this was `all`, the concept is not exposed.")
    print("\nDENSITY GUARD: below 50% coverage a field cannot be read on deciles at all.")
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
    parser.add_argument("--print-expressions", action="store_true",
                        help="offline: dump every expression for copy-paste, then exit")
    parser.add_argument("--score-manual", type=Path, metavar="FILE",
                        help="offline: score decile returns typed in from the web UI")
    parser.add_argument("--phase0", action="store_true",
                        help="one command: dump every relevant dataset's fields to CSV "
                             "and resolve the nine field ids our signals need")
    parser.add_argument("--list-datasets", action="store_true",
                        help="Phase 0: list available datasets, then exit")
    parser.add_argument("--dump-fields", metavar="DATASET_ID",
                        help="Phase 0: download a dataset's whole field dictionary to CSV")
    parser.add_argument("--find-field", nargs=2, metavar=("DATASET_ID", "TEXT"),
                        help="Phase 0: search a dataset's fields by id or description; "
                             "pass DATASET_ID=all to sweep every dataset")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "evidence/worldquant_brain_decile_ladder_v1")
    args = parser.parse_args()

    if args.print_expressions:
        return print_expressions(args.signals, args.group)
    if args.score_manual:
        return score_manual(args.score_manual)

    session = login(args.credentials)

    if args.phase0:
        return phase0(session, Path(__file__).resolve().parents[1])
    if args.list_datasets:
        return list_datasets(session)
    if args.dump_fields:
        return dump_fields(session, args.dump_fields,
                           Path(__file__).resolve().parents[1]
                           / f"data/worldquant_brain_fields/{args.dump_fields}.csv")
    if args.find_field:
        return find_field(session, args.find_field[0], args.find_field[1])

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

        shape = ladder_shape(ladder)
        summary[signal] = dict(shape, decile_returns=ladder, checks=records)
        print("  ---", flush=True)
        report(signal, shape)

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
