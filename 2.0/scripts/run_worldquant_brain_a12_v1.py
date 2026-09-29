"""A12: five NEW hypotheses on WorldQuant BRAIN, scored by decile shape against a
coverage-matched no-skill control. Pre-registered in config/worldquant_brain_a12_v1.json
(human-readable: docs/BRAIN_A12_PREREGISTRATION_V1.md), committed before the first simulation.

Different from run_worldquant_brain_search_v1.py in three recorded ways:
  * the expressions, signs, variants, controls and bar are read from the frozen config, not
    typed here, so the script cannot drift from the registration;
  * every simulation is cached to evidence/worldquant_brain_a12_v1/sims/<label>.json the moment
    it finishes, so a crash or an expired session loses nothing (Step 317 lost two results to
    an end-of-run write);
  * it runs up to three simulations concurrently under one global rate limiter, because 241
    sequential simulations is most of a day. BRAIN's limit is 50 requests/minute; this stays
    under 40.

Phases, in order:  --phase probes   density guard on the zero-prone variants (H1, H5)
                   --phase ladders  production form + ten-decile ladder for each readable variant
                   --phase controls four coverage-matched cap controls
                   --phase desize   conditional; only for a variant that met bars 1-5
                   --phase score    offline: shapes, verdicts, control comparison, permutation p,
                                    yearly regime check, summary.csv

Nothing here submits anything. Simulations only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "ladder", Path(__file__).with_name("run_worldquant_brain_decile_ladder_v1.py"))
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)

CONFIG = ROOT / "config/worldquant_brain_a12_v1.json"
OUT = ROOT / "evidence/worldquant_brain_a12_v1"
SIMS = OUT / "sims"
UNIVERSE = 3000


# ---------------------------------------------------------------------------- rate limit
class RateLimiter:
    """Global spacing between requests across threads. 60/1.6 = 37.5 requests a minute."""

    def __init__(self, interval: float = 1.6):
        self.interval, self.lock, self.last = interval, threading.Lock(), 0.0

    def wait(self) -> None:
        with self.lock:
            pause = self.last + self.interval - time.time()
            if pause > 0:
                time.sleep(pause)
            self.last = time.time()


LIMIT = RateLimiter()
_local = threading.local()
CREDENTIALS = Path.home() / ".worldquant_brain.json"


def session() -> requests.Session:
    if getattr(_local, "session", None) is None:
        LIMIT.wait()
        _local.session = L.login(CREDENTIALS)
    return _local.session


def _request(method: str, url: str, **kw) -> requests.Response | None:
    for attempt in range(8):
        LIMIT.wait()
        try:
            response = session().request(method, url, timeout=L.HTTP_TIMEOUT, **kw)
        except requests.RequestException:
            time.sleep(10.0)
            continue
        if response.status_code == 401:
            LIMIT.wait()
            L.relogin(session())
            continue
        if response.status_code == 429:
            time.sleep(min(90.0, 15.0 * (attempt + 1)))
            continue
        return response
    return None


def simulate(expression: str, neutralization: str, timeout: int = 1800) -> dict:
    """POST, poll slowly, fetch the alpha and its yearly-stats. Never raises."""
    settings = dict(L.BASE_SETTINGS, neutralization=neutralization)
    payload = {"type": "REGULAR", "settings": settings, "regular": expression}
    location = None
    for attempt in range(30):                       # concurrency limit shows up as 429 on POST
        response = _request("POST", f"{L.API}/simulations", json=payload)
        if response is None:
            return {"error": "POST failed repeatedly"}
        if response.status_code == 201:
            location = response.headers.get("Location", "").rstrip("/")
            break
        text = response.text[:400]
        if "CONCURRENT" in text.upper() or response.status_code == 429:
            time.sleep(30.0)
            continue
        return {"error": f"POST {response.status_code} {text}"}
    if not location:
        return {"error": "could not start simulation (concurrency limit)"}

    deadline = time.time() + timeout
    state: dict = {}
    while time.time() < deadline:
        poll = _request("GET", location)
        if poll is None or poll.status_code != 200:
            time.sleep(15.0)
            continue
        retry = float(poll.headers.get("Retry-After", 0) or 0)
        if retry > 0:
            time.sleep(max(retry, 8.0))
            continue
        state = poll.json()
        status = state.get("status")
        # WARNING with an alpha id is a finished simulation carrying a notice -- found on the
        # controls, where `cap + 0 * <field>` trips BRAIN's unit check ("Incompatible unit for
        # input of add"). The first run treated it as still running and timed out after 30 min.
        if status == "COMPLETE" or (status == "WARNING" and state.get("alpha")):
            break
        if status in {"FAILED", "ERROR"}:
            return {"error": f"{status}: {json.dumps(state)[:600]}"}
        time.sleep(8.0)
    else:
        return {"error": f"timed out: {json.dumps(state)[:300]}"}

    return fetch_alpha(state, expression, neutralization)


def fetch_alpha(state: dict, expression: str, neutralization: str) -> dict:
    alpha_id = state.get("alpha")
    if not alpha_id:
        return {"error": f"complete without alpha id: {json.dumps(state)[:300]}"}
    alpha = _request("GET", f"{L.API}/alphas/{alpha_id}")
    if alpha is None or alpha.status_code != 200:
        return {"error": f"alpha fetch failed for {alpha_id}", "alpha_id": alpha_id}
    record = alpha.json()
    yearly = None
    for _ in range(20):
        response = _request("GET", f"{L.API}/alphas/{alpha_id}/recordsets/yearly-stats")
        if response is not None and response.status_code == 200 and response.text:
            yearly = response.json()
            break
        time.sleep(4.0)
    return {"alpha_id": alpha_id, "is": record.get("is"), "settings": record.get("settings"),
            "expression": expression, "neutralization": neutralization, "yearly": yearly,
            "status": state.get("status"), "message": state.get("message")}


def recover(label: str, expression: str, neutralization: str) -> dict | None:
    """A cached error that names a simulation id may have finished after we stopped waiting.
    Fetch it rather than re-simulate: a re-simulation would be a second, uncounted trial."""
    import re
    path = SIMS / f"{label}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    match = re.search(r'"id": "([A-Za-z0-9]{12,})"', data.get("error", ""))
    if not match:
        return None
    poll = _request("GET", f"{L.API}/simulations/{match.group(1)}")
    if poll is None or poll.status_code != 200 or not poll.text:
        return None
    state = poll.json()
    if not state.get("alpha"):
        return None
    result = fetch_alpha(state, expression, neutralization)
    if "error" in result:
        return None
    result["label"], result["recovered_from_timeout"] = label, True
    path.write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


# ---------------------------------------------------------------------------- cache
def cached(label: str) -> dict | None:
    path = SIMS / f"{label}.json"
    if path.exists():
        data = json.loads(path.read_text())
        if "error" not in data:
            return data
    return None


def run_jobs(jobs: list[tuple[str, str, str]], workers: int) -> dict[str, dict]:
    """jobs: (label, expression, neutralization). Cached labels are skipped."""
    SIMS.mkdir(parents=True, exist_ok=True)
    results = {label: cached(label) or recover(label, e, n) for label, e, n in jobs}
    todo = [job for job in jobs if results[job[0]] is None]
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo)} cached, {len(todo)} to run", flush=True)

    def one(job):
        label, expression, neutralization = job
        started = time.time()
        result = simulate(expression, neutralization)
        result["label"], result["seconds"] = label, round(time.time() - started, 1)
        (SIMS / f"{label}.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        return label, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one, job) for job in todo]):
            label, result = future.result()
            results[label] = result
            if "error" in result:
                print(f"  {label}: ERROR {result['error'][:160]}", flush=True)
            else:
                stats = result["is"] or {}
                print(f"  {label}: {result['seconds']:.0f}s returns {stats.get('returns')} "
                      f"long {stats.get('longCount')} short {stats.get('shortCount')}", flush=True)
    return results


# ---------------------------------------------------------------------------- expressions
def band(expression: str, decile: int) -> str:
    lo = -1.0 if decile == 1 else (decile - 1) / 10.0
    return (f"if_else(rank({expression}) > {lo}, 1, 0)"
            f" - if_else(rank({expression}) > {decile / 10.0}, 1, 0)")


def variants(config: dict) -> dict[str, tuple[str, str, dict]]:
    out = {}
    for hyp, spec in config["hypotheses"].items():
        for name, expression in spec["variants"].items():
            out[name] = (hyp, expression, spec)
    return out


def inner(expression: str) -> str:
    """The argument of the outer group_rank(..., sector), for the de-sized form."""
    head, tail = "group_rank(", ", sector)"
    assert expression.startswith(head) and expression.endswith(tail), expression
    return expression[len(head):-len(tail)]


# ---------------------------------------------------------------------------- phases
def phase_probes(config: dict, workers: int) -> int:
    jobs = []
    for name, (hyp, expression, spec) in variants(config).items():
        if name in spec.get("density_probe_on", []):
            jobs.append((f"probe_{name}", f"if_else(abs({expression}) > 0, 1, 0)",
                         config["settings"]["density_probe_neutralization"]))
    results = run_jobs(jobs, workers)
    density = {}
    for label, result in results.items():
        name = label[len("probe_"):]
        if "error" in result:
            density[name] = {"readable": False, "reason": f"probe failed: {result['error'][:200]}"}
            continue
        stats = result["is"] or {}
        nonzero, zero = stats.get("longCount") or 0, stats.get("shortCount") or 0
        share = nonzero / UNIVERSE
        density[name] = {"nonzero_names": nonzero, "zero_names": zero,
                         "density_of_universe": round(share, 4),
                         "nonzero_share_of_scored": round(nonzero / max(nonzero + zero, 1), 4),
                         "yearly": _yearly_counts(result),
                         "readable": share >= 0.5,
                         "reason": "density >= 0.50" if share >= 0.5 else
                         f"UNREADABLE: only {share:.1%} of the universe carries a non-zero value"}
        print(f"  {name}: {json.dumps(density[name])}", flush=True)
    (OUT / "density.json").write_text(json.dumps(density, indent=2, sort_keys=True))
    return 0


def _yearly_counts(result: dict) -> dict:
    yearly = (result.get("yearly") or {}).get("records") or []
    return {row[0]: {"long": row[3], "short": row[4]} for row in yearly}


def readable(name: str) -> bool:
    path = OUT / "density.json"
    density = json.loads(path.read_text()) if path.exists() else {}
    return density.get(name, {"readable": True})["readable"]


def phase_ladders(config: dict, workers: int, only: list[str] | None) -> int:
    jobs = []
    ladder_n = config["settings"]["ladder_neutralization"]
    prod_n = config["settings"]["production_neutralization"]
    for name, (hyp, expression, spec) in variants(config).items():
        if only and name not in only:
            continue
        if name in spec.get("density_probe_on", []) and not (OUT / "density.json").exists():
            raise SystemExit("run --phase probes first: the density guard comes before any ladder")
        if not readable(name):
            print(f"  {name}: skipped, failed the density guard", flush=True)
            continue
        jobs.append((f"{name}_production", expression, prod_n))
        jobs.extend((f"{name}_d{d:02d}", band(expression, d), ladder_n) for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


def phase_controls(config: dict, workers: int, only: list[str] | None = None) -> int:
    ladder_n = config["settings"]["ladder_neutralization"]
    jobs = []
    for cid, expression in config["controls"].items():
        if not cid.startswith("C") or (only and cid not in only):
            continue
        jobs.extend((f"control_{cid}_d{d:02d}", band(expression, d), ladder_n) for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


def phase_addendum(config: dict, workers: int) -> int:
    """Addendum 1 (kill-only): momentum control and momentum-neutral H1c on H1's mask."""
    spec = config["addendum_1_mid_run"]
    ladder_n = config["settings"]["ladder_neutralization"]
    jobs = []
    for label, key in (("addendum_M1_momentum", "momentum_control_M1"),
                       ("addendum_H1c_momentum_neutral", "momentum_neutral_H1c")):
        jobs.extend((f"{label}_d{d:02d}", band(spec[key], d), ladder_n) for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


def phase_desize(config: dict, workers: int, names: list[str]) -> int:
    if len(names) > config["budget"]["conditional_desized_ladders_max"]:
        raise SystemExit("more de-sized ladders than the registered budget allows")
    ladder_n = config["settings"]["ladder_neutralization"]
    table = variants(config)
    jobs = []
    for name in names:
        expression = f"group_rank({inner(table[name][1])}, bucket(rank(cap), buckets=5))"
        jobs.extend((f"{name}_desized_d{d:02d}", band(expression, d), ladder_n)
                    for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


# ---------------------------------------------------------------------------- scoring
def ladder_from_cache(prefix: str) -> tuple[dict, dict, dict, list[str]]:
    returns, counts, yearly, missing = {}, {}, {}, []
    for d in range(1, 11):
        result = cached(f"{prefix}_d{d:02d}")
        if result is None:
            returns[d] = float("nan")
            missing.append(f"{prefix}_d{d:02d}")
            continue
        stats = result["is"] or {}
        returns[d] = float(stats.get("returns", float("nan")))
        counts[d] = (stats.get("longCount") or 0, stats.get("shortCount") or 0)
        for row in ((result.get("yearly") or {}).get("records") or []):
            yearly.setdefault(row[0], {})[d] = float(row[7])
    return returns, counts, yearly, missing


def tie_check(counts: dict) -> tuple[bool, list]:
    shares = []
    for d in range(1, 11):
        long_, short = counts.get(d, (0, 0))
        shares.append(round(long_ / max(long_ + short, 1), 4))
    return all(0.05 <= s <= 0.15 for s in shares), shares


def permutation_p(returns: dict, full: float, middle: float, draws: int = 200_000,
                  seed: int = 20260929) -> float:
    """P[full >= obs AND middle-8 >= obs] over random orderings of the ten decile returns."""
    values = [returns[d] for d in range(1, 11)]
    if any(v != v for v in values) or full != full or middle != middle:
        return float("nan")
    rng = random.Random(seed)
    hits = 0
    for _ in range(draws):
        rng.shuffle(values)
        shuffled = {d + 1: v for d, v in enumerate(values)}
        f = L.monotonicity(shuffled)
        if f != f or f < full - 1e-12:
            continue
        m = L.monotonicity({d: shuffled[d] for d in range(2, 10)})
        if m == m and m >= middle - 1e-12:
            hits += 1
    return (hits + 1) / (draws + 1)


def bh(pvalues: dict[str, float], q: float = 0.05) -> dict[str, bool]:
    items = sorted((p, k) for k, p in pvalues.items() if p == p)
    m, cutoff = len(items), 0
    for i, (p, _) in enumerate(items, 1):
        if p <= q * i / m:
            cutoff = i
    passed = {k for _, k in items[:cutoff]}
    return {k: k in passed for k in pvalues}


def score_prefix(prefix: str, draws: int) -> dict:
    returns, counts, yearly, missing = ladder_from_cache(prefix)
    shape = L.ladder_shape(returns)
    ties_ok, shares = tie_check(counts)
    years = {}
    for year, ladder in sorted(yearly.items()):
        if len(ladder) == 10:
            years[year] = {"monotonicity": L.monotonicity(ladder),
                           "top_minus_bottom": ladder[10] - ladder[1]}
    scored = [sum(counts[d]) for d in counts]
    return dict(shape, decile_returns=returns, decile_share_of_scored=shares,
                tie_check_passed=ties_ok, missing=missing,
                scored_names_mean=round(sum(scored) / len(scored), 1) if scored else None,
                verdict=L.verdict(shape) if not missing else "INCOMPLETE -- deciles missing",
                permutation_p=(permutation_p(returns, shape["monotonicity"],
                                             shape["monotonicity_middle_8"], draws)
                               if not missing else float("nan")),
                yearly=years)


def phase_score(config: dict, draws: int) -> int:
    reading = config["reading"]["multiple_testing"]
    n_conservative = reading["prior_simulations_on_account_at_registration"] + reading["a12_constructions"]
    n_constructions = 19 + reading["a12_constructions"]
    density = json.loads((OUT / "density.json").read_text()) if (OUT / "density.json").exists() else {}

    controls = {}
    for cid in (c for c in config["controls"] if c.startswith("C")):
        if not cached(f"control_{cid}_d01"):
            continue                    # a control is only run when a hypothesis it serves is readable
        controls[cid] = score_prefix(f"control_{cid}", draws)
        controls[cid]["expression"] = config["controls"][cid]
        print(f"control {cid}: full {controls[cid]['monotonicity']:+.3f} "
              f"mid8 {controls[cid]['monotonicity_middle_8']:+.3f} "
              f"scored {controls[cid]['scored_names_mean']}", flush=True)

    rows, pvals = [], {}
    results = {}
    for name, (hyp, expression, spec) in variants(config).items():
        record = {"hypothesis": hyp, "variant": name, "expression": expression,
                  "declared_sign": spec["sign"], "fields": spec["fields"],
                  "control": spec["control"], "density": density.get(name)}
        if not readable(name):
            record["verdict"] = density[name]["reason"]
            record["status"] = "UNREADABLE (density)"
        else:
            record.update(score_prefix(name, draws))
            production = cached(f"{name}_production")
            record["production_not_evidence"] = (production or {}).get("is")
            record["production_alpha_id"] = (production or {}).get("alpha_id")
            control = controls[spec["control"]]
            record["control_full"] = control["monotonicity"]
            record["control_middle_8"] = control["monotonicity_middle_8"]
            record["control_scored_names_mean"] = control["scored_names_mean"]
            beats = (record["monotonicity"] == record["monotonicity"]
                     and record["monotonicity"] > control["monotonicity"]
                     and record["monotonicity_middle_8"] == record["monotonicity_middle_8"]
                     and record["monotonicity_middle_8"] > control["monotonicity_middle_8"])
            record["beats_control_both"] = bool(beats)
            positive_years = sum(1 for y in record["yearly"].values()
                                 if y["monotonicity"] == y["monotonicity"] and y["monotonicity"] > 0)
            record["years_positive"] = f"{positive_years}/{len(record['yearly'])}"
            if not record["tie_check_passed"]:
                record["status"] = "UNREADABLE (ties)"
            else:
                record["status"] = "scored"
                pvals[name] = record["permutation_p"]
            record["bars"] = {
                "1_orders_its_deciles": record["verdict"].startswith("ORDERS"),
                "2_beats_control": record["beats_control_both"],
                "3_tie_check": record["tie_check_passed"],
                "4_bonferroni_conservative": (record["permutation_p"] == record["permutation_p"]
                                              and record["permutation_p"] < 0.05 / n_conservative),
                "5_regime_4_of_5": positive_years >= 4,
            }
            record["lead_before_desizing"] = all(record["bars"].values())
            desized = score_prefix(f"{name}_desized", draws) if cached(f"{name}_desized_d01") else None
            record["desized"] = desized
        results[name] = record
        (OUT / f"{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True, default=str))

    fdr = bh(pvals)
    for name, record in results.items():
        record["bh_fdr_pass"] = fdr.get(name, False)
        (OUT / f"{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True, default=str))
        prod = record.get("production_not_evidence") or {}
        rows.append({
            "hypothesis": record["hypothesis"], "variant": name, "status": record["status"],
            "density_of_universe": (record.get("density") or {}).get("density_of_universe", ""),
            "scored_names": record.get("scored_names_mean", ""),
            "monotonicity": _f(record.get("monotonicity")),
            "middle_8": _f(record.get("monotonicity_middle_8")),
            "top_minus_bottom": _f(record.get("top_minus_bottom")),
            "control": record["control"], "control_full": _f(record.get("control_full")),
            "control_middle_8": _f(record.get("control_middle_8")),
            "beats_control_both": record.get("beats_control_both", ""),
            "permutation_p": _f(record.get("permutation_p"), 6),
            "bonferroni_conservative_bar": f"{0.05 / n_conservative:.6f}",
            "bonferroni_constructions_bar": f"{0.05 / n_constructions:.6f}",
            "bh_fdr_pass": record.get("bh_fdr_pass"),
            "years_positive": record.get("years_positive", ""),
            "lead_before_desizing": record.get("lead_before_desizing", False),
            "verdict": record["verdict"],
            "brain_sharpe_NOT_EVIDENCE": prod.get("sharpe", ""),
            "brain_turnover_NOT_EVIDENCE": prod.get("turnover", ""),
            "brain_returns_NOT_EVIDENCE": prod.get("returns", ""),
            "brain_fitness_NOT_EVIDENCE": prod.get("fitness", ""),
        })
        print(f"{name:24} {record['status']:22} mono {_f(record.get('monotonicity'))} "
              f"mid8 {_f(record.get('monotonicity_middle_8'))} p {_f(record.get('permutation_p'), 5)} "
              f"| {record['verdict'][:70]}", flush=True)

    with (OUT / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True, default=str))
    window = next((c.get("settings") for c in (cached(p.stem) for p in SIMS.glob("*.json")) if c), {})
    (OUT / "run_meta.json").write_text(json.dumps({
        "window": {"start": (window or {}).get("startDate"), "end": (window or {}).get("endDate")},
        "simulations_run": len(list(SIMS.glob("*.json"))),
        "bonferroni_denominator_conservative": n_conservative,
        "bonferroni_denominator_constructions": n_constructions,
        "permutation_draws": draws}, indent=2))
    return 0


def _f(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return f"{value:+.{digits}f}" if digits <= 3 else f"{value:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True,
                        choices=["probes", "ladders", "controls", "addendum", "desize", "score"])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--only", nargs="*", help="restrict --phase ladders to these variants")
    parser.add_argument("--desize", nargs="*", default=[], help="variants for --phase desize")
    parser.add_argument("--draws", type=int, default=200_000)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    if args.phase == "probes":
        return phase_probes(config, args.workers)
    if args.phase == "ladders":
        return phase_ladders(config, args.workers, args.only)
    if args.phase == "controls":
        return phase_controls(config, args.workers, args.only)
    if args.phase == "addendum":
        return phase_addendum(config, args.workers)
    if args.phase == "desize":
        return phase_desize(config, args.workers, args.desize)
    return phase_score(config, args.draws)


if __name__ == "__main__":
    raise SystemExit(main())
