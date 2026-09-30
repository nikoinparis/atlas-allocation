"""A15: five hypotheses on WorldQuant BRAIN under a HOLDOUT design (train 2019-2022, hold out 2023).

Pre-registered in config/worldquant_brain_a15_v1.json (human-readable:
docs/BRAIN_A15_PREREGISTRATION_V1.md), committed before the first simulation.

Reuses run_worldquant_brain_a12_v1.py for everything that touches the platform (rate limiter,
login, simulate with the WARNING-with-alpha fix, timeout recovery, decile band expression,
permutation test, BH) and only redirects its cache to evidence/worldquant_brain_a15_v1/sims.
What is new is the blindness:

  * nothing printed or scored before --phase holdout uses a full-window statistic or a 2023
    row. Train ladders are built from BRAIN's yearly-stats rows 2019-2022 only;
  * --phase holdout refuses to run unless docs/BRAIN_A15_TRAIN_FREEZE_V1.md is committed and
    clean in git.

Phases, in order:
  --phase probes    density guard on the raw inner signal of all 15 variants (counts only)
  --phase ladders   production form + ten-decile ladder for each readable variant
  --phase controls  coverage-matched cap controls for hypotheses with a readable variant
  --phase train     offline: 2019-2022 shapes, bars T1-T5, best-variant choice -> train.json
  --phase kill      de-sized and momentum-neutral ladders for qualifying frozen variants
  --phase trainkill offline: train read of the kill ladders -> train_kill.json
  --phase holdout   offline, ONCE, after the freeze commit: full window + 2023

Nothing here submits anything.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "a12", Path(__file__).with_name("run_worldquant_brain_a12_v1.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
L = A.L

CONFIG = ROOT / "config/worldquant_brain_a15_v1.json"
OUT = ROOT / "evidence/worldquant_brain_a15_v1"
SIMS = OUT / "sims"
FREEZE = ROOT / "docs/BRAIN_A15_TRAIN_FREEZE_V1.md"
A.OUT, A.SIMS = OUT, SIMS           # redirect the A12 cache helpers to A15's own directory
TRAIN = ("2019", "2020", "2021", "2022")
HOLD = "2023"
UNIVERSE = 3000


# ---------------------------------------------------------------------------- helpers
def variants(config: dict) -> dict[str, tuple[str, str, dict]]:
    return {name: (hyp, expr, spec) for hyp, spec in config["hypotheses"].items()
            for name, expr in spec["variants"].items()}


def split_group(expression: str) -> tuple[str, str]:
    """group_rank(<inner>, <group>) -> (inner, group)."""
    assert expression.startswith("group_rank(") and expression.endswith(")"), expression
    body = expression[len("group_rank("):-1]
    depth = 0
    for i in range(len(body) - 1, -1, -1):
        ch = body[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            depth -= 1
        elif ch == "," and depth == 0:
            return body[:i].strip(), body[i + 1:].strip()
    raise ValueError(expression)


def run_jobs(jobs: list[tuple[str, str, str]], workers: int) -> dict[str, dict]:
    """A12's run_jobs without the full-window `returns` print (blindness)."""
    SIMS.mkdir(parents=True, exist_ok=True)
    results = {label: A.cached(label) or A.recover(label, e, n) for label, e, n in jobs}
    todo = [job for job in jobs if results[job[0]] is None]
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo)} cached, {len(todo)} to run", flush=True)

    def one(job):
        label, expression, neutralization = job
        started = time.time()
        result = A.simulate(expression, neutralization)
        result["label"], result["seconds"] = label, round(time.time() - started, 1)
        (SIMS / f"{label}.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        return label, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one, job) for job in todo]):
            label, result = future.result()
            results[label] = result
            if "error" in result:
                print(f"  {label}: ERROR {result['error'][:300]}", flush=True)
            else:
                print(f"  {label}: done in {result['seconds']:.0f}s", flush=True)
    return results


def yearly_rows(result: dict) -> dict[str, list]:
    return {row[0]: row for row in ((result.get("yearly") or {}).get("records") or [])}


def density(name: str) -> dict:
    path = OUT / "density.json"
    return json.loads(path.read_text()).get(name, {}) if path.exists() else {}


def readable(name: str) -> bool:
    return bool(density(name).get("readable"))


def ladder_years(prefix: str, years: tuple[str, ...]) -> tuple[dict, dict, dict, list]:
    """Per-decile mean yearly return over `years`, per-year ladders, mean counts."""
    mean, per_year, counts, missing = {}, {}, {}, []
    for d in range(1, 11):
        result = A.cached(f"{prefix}_d{d:02d}")
        rows = yearly_rows(result) if result else {}
        if not result or any(y not in rows for y in years):
            mean[d] = float("nan")
            missing.append(f"{prefix}_d{d:02d}")
            continue
        mean[d] = sum(float(rows[y][7]) for y in years) / len(years)
        counts[d] = (sum(rows[y][3] for y in years) / len(years),
                     sum(rows[y][4] for y in years) / len(years))
        for y in years:
            per_year.setdefault(y, {})[d] = float(rows[y][7])
    return mean, per_year, counts, missing


def score_years(prefix: str, years: tuple[str, ...], draws: int) -> dict:
    mean, per_year, counts, missing = ladder_years(prefix, years)
    shape = L.ladder_shape(mean)
    ties_ok, shares = A.tie_check(counts)
    yearly = {y: {"monotonicity": L.monotonicity(lad), "top_minus_bottom": lad[10] - lad[1]}
              for y, lad in sorted(per_year.items()) if len(lad) == 10}
    scored = [sum(c) for c in counts.values()]
    return dict(shape, decile_returns=mean, decile_share_of_scored=shares, tie_check_passed=ties_ok,
                missing=missing, yearly=yearly,
                scored_names_mean=round(sum(scored) / len(scored), 1) if scored else None,
                verdict=L.verdict(shape) if not missing else "INCOMPLETE -- deciles missing",
                permutation_p=(A.permutation_p(mean, shape["monotonicity"],
                                               shape["monotonicity_middle_8"], draws)
                               if not missing else float("nan")))


def score_full(prefix: str, draws: int) -> dict:
    """Full window (BRAIN's `is` block). ONLY called from --phase holdout."""
    returns, counts, missing = {}, {}, []
    for d in range(1, 11):
        result = A.cached(f"{prefix}_d{d:02d}")
        if result is None:
            returns[d] = float("nan")
            missing.append(d)
            continue
        stats = result["is"] or {}
        returns[d] = float(stats.get("returns", float("nan")))
        counts[d] = (stats.get("longCount") or 0, stats.get("shortCount") or 0)
    shape = L.ladder_shape(returns)
    ties_ok, shares = A.tie_check(counts)
    return dict(shape, decile_returns=returns, tie_check_passed=ties_ok, missing=missing,
                verdict=L.verdict(shape) if not missing else "INCOMPLETE",
                permutation_p=(A.permutation_p(returns, shape["monotonicity"],
                                               shape["monotonicity_middle_8"], draws)
                               if not missing else float("nan")))


def _f(v, digits: int = 3) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:+.{digits}f}" if digits <= 3 else f"{v:.{digits}g}"


# ---------------------------------------------------------------------------- phases
def phase_probes(config: dict, workers: int) -> int:
    neut = config["settings"]["density_probe_neutralization"]
    jobs = []
    for name, (_, expression, _) in variants(config).items():
        inner, _group = split_group(expression)
        jobs.append((f"probe_{name}", f"if_else(abs({inner}) > 0, 1, 0)", neut))
    results = run_jobs(jobs, workers)
    out = {}
    for label, result in results.items():
        name = label[len("probe_"):]
        if "error" in result:
            out[name] = {"readable": False, "reason": f"probe failed: {result['error'][:300]}"}
        else:
            stats = result["is"] or {}
            nonzero, zero = stats.get("longCount") or 0, stats.get("shortCount") or 0
            share = nonzero / UNIVERSE
            out[name] = {"nonzero_names": nonzero, "zero_names": zero,
                         "density_of_universe": round(share, 4),
                         "nonzero_share_of_scored": round(nonzero / max(nonzero + zero, 1), 4),
                         "yearly_counts": {y: {"nonzero": r[3], "zero": r[4]}
                                           for y, r in yearly_rows(result).items()},
                         "readable": share >= 0.5,
                         "reason": "density >= 0.50" if share >= 0.5 else
                         f"UNREADABLE: only {share:.1%} of the universe carries a non-zero value"}
        print(f"  {name:22} density {out[name].get('density_of_universe')} "
              f"readable {out[name]['readable']}  {out[name]['reason'][:80]}", flush=True)
    (OUT / "density.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    return 0


def phase_ladders(config: dict, workers: int, only: list[str] | None) -> int:
    if not (OUT / "density.json").exists():
        raise SystemExit("run --phase probes first")
    s = config["settings"]
    jobs = []
    for name, (_, expression, _) in variants(config).items():
        if only and name not in only:
            continue
        if not readable(name):
            print(f"  {name}: skipped, failed the density guard", flush=True)
            continue
        jobs.append((f"{name}_production", expression, s["production_neutralization"]))
        jobs.extend((f"{name}_d{d:02d}", A.band(expression, d), s["ladder_neutralization"])
                    for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


def phase_controls(config: dict, workers: int) -> int:
    table = variants(config)
    jobs = []
    for hyp, spec in config["hypotheses"].items():
        if not any(readable(n) for n in spec["variants"]):
            print(f"  {spec['control']}: not run, no readable variant in {hyp}", flush=True)
            continue
        expression = config["controls"][spec["control"]]
        jobs.extend((f"control_{spec['control']}_d{d:02d}", A.band(expression, d),
                     config["settings"]["ladder_neutralization"]) for d in range(1, 11))
    run_jobs(jobs, workers)
    return 0


def train_turnover(name: str) -> float:
    result = A.cached(f"{name}_production")
    rows = yearly_rows(result) if result else {}
    vals = [float(rows[y][5]) for y in TRAIN if y in rows]
    return sum(vals) / len(vals) if vals else float("nan")


def phase_train(config: dict, draws: int) -> int:
    bar = config["reading"]["multiple_testing"]["train_bonferroni_denominator"]
    controls = {}
    for spec in config["hypotheses"].values():
        cid = spec["control"]
        if A.cached(f"control_{cid}_d01"):
            controls[cid] = score_years(f"control_{cid}", TRAIN, draws)
    records, best = {}, {}
    for hyp, spec in config["hypotheses"].items():
        candidates = []
        for name, expression in spec["variants"].items():
            rec = {"hypothesis": hyp, "variant": name, "expression": expression,
                   "density": density(name)}
            if not readable(name):
                rec["status"] = "UNREADABLE (density)"
                records[name] = rec
                continue
            rec.update(score_years(name, TRAIN, draws))
            ctl = controls.get(spec["control"])
            rec["control"] = spec["control"]
            if ctl is None or not ctl["tie_check_passed"]:
                rec["control_status"] = "UNREADABLE control" if ctl else "control missing"
                beats = None
            else:
                rec["control_train_full"] = ctl["monotonicity"]
                rec["control_train_middle_8"] = ctl["monotonicity_middle_8"]
                rec["control_scored_names_mean"] = ctl["scored_names_mean"]
                beats = bool(rec["monotonicity"] > ctl["monotonicity"]
                             and rec["monotonicity_middle_8"] > ctl["monotonicity_middle_8"])
            pos = sum(1 for y in rec["yearly"].values() if y["monotonicity"] == y["monotonicity"]
                      and y["monotonicity"] > 0)
            rec["train_years_positive"] = f"{pos}/{len(rec['yearly'])}"
            rec["train_turnover_production_2019_2022"] = train_turnover(name)
            rec["bars"] = {
                "T1_orders": rec["verdict"].startswith("ORDERS"),
                "T2_beats_control": beats,
                "T3_tie_check": rec["tie_check_passed"],
                "T4_3_of_4_years": pos >= 3,
                "T5_bonferroni_train": bool(rec["permutation_p"] == rec["permutation_p"]
                                            and rec["permutation_p"] < 0.05 / bar),
            }
            rec["passes_train"] = all(v is True for v in rec["bars"].values())
            rec["status"] = "scored" if rec["tie_check_passed"] else "UNREADABLE (ties)"
            records[name] = rec
            if rec["tie_check_passed"] and rec["monotonicity"] == rec["monotonicity"]:
                candidates.append(rec)
        passing = [r for r in candidates if r["passes_train"]]
        pool = passing or candidates
        if pool:
            def key(r):
                mid = r["monotonicity_middle_8"]
                mid = mid if mid == mid else -9
                t = r["train_turnover_production_2019_2022"]
                return (-(r["monotonicity"] + mid), t if t == t else 9)
            chosen = sorted(pool, key=key)[0]
            best[hyp] = {"variant": chosen["variant"], "passes_train": chosen["passes_train"],
                         "can_pass": chosen["passes_train"]}
        else:
            best[hyp] = {"variant": None, "passes_train": False, "can_pass": False,
                         "reason": "no readable, tie-checked variant"}
    qualifying = sorted([h for h, b in best.items() if b["passes_train"]],
                        key=lambda h: -(records[best[h]["variant"]]["monotonicity"]
                                        + records[best[h]["variant"]]["monotonicity_middle_8"]))
    kill_list = qualifying[:config["budget"]["conditional_kill_hypotheses_max"]]
    out = {"train_years": TRAIN, "bonferroni_train_bar": 0.05 / bar, "controls": controls,
           "variants": records, "best": best, "kill_tests_for": kill_list}
    (OUT / "train.json").write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    for cid, c in controls.items():
        print(f"control {cid}: train full {_f(c['monotonicity'])} mid8 {_f(c['monotonicity_middle_8'])} "
              f"ties_ok {c['tie_check_passed']} scored {c['scored_names_mean']}")
    rows = []
    for name, r in records.items():
        rows.append({"hypothesis": r["hypothesis"], "variant": name, "status": r["status"],
                     "density": (r.get("density") or {}).get("density_of_universe", ""),
                     "train_full": _f(r.get("monotonicity")),
                     "train_middle_8": _f(r.get("monotonicity_middle_8")),
                     "train_top_minus_bottom": _f(r.get("top_minus_bottom"), 3),
                     "train_years_positive": r.get("train_years_positive", ""),
                     "control_train_full": _f(r.get("control_train_full")),
                     "control_train_middle_8": _f(r.get("control_train_middle_8")),
                     "train_permutation_p": _f(r.get("permutation_p"), 6),
                     "passes_train": r.get("passes_train", False),
                     "verdict_train": r.get("verdict", r["status"])})
        print(f"{name:22} {r['status']:20} full {_f(r.get('monotonicity'))} mid8 "
              f"{_f(r.get('monotonicity_middle_8'))} tmb {_f(r.get('top_minus_bottom'))} "
              f"yrs {r.get('train_years_positive', '')} p {_f(r.get('permutation_p'), 6)} "
              f"pass {r.get('passes_train', False)} | {str(r.get('verdict', ''))[:44]}")
    with (OUT / "train_summary.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("best:", json.dumps(best), "\nkill tests for:", kill_list)
    return 0


def kill_expressions(expression: str) -> dict[str, str]:
    inner, _ = split_group(expression)
    return {"K1_desized": f'group_rank({inner}, bucket(rank(cap), range="0,1,0.2"))',
            "K2_momentum_neutral": f'group_rank({inner}, bucket(rank(ts_sum(returns, 63)), range="0,1,0.2"))'}


def phase_kill(config: dict, workers: int) -> int:
    train = json.loads((OUT / "train.json").read_text())
    table = variants(config)
    jobs = []
    for hyp in train["kill_tests_for"]:
        name = train["best"][hyp]["variant"]
        for key, expression in kill_expressions(table[name][1]).items():
            jobs.extend((f"{name}_{key}_d{d:02d}", A.band(expression, d),
                         config["settings"]["ladder_neutralization"]) for d in range(1, 11))
    if len(jobs) > config["budget"]["conditional_kill_simulations_max"]:
        raise SystemExit("more kill simulations than registered")
    run_jobs(jobs, workers)
    return 0


def phase_trainkill(config: dict, draws: int) -> int:
    train = json.loads((OUT / "train.json").read_text())
    out = {}
    for hyp in train["kill_tests_for"]:
        name = train["best"][hyp]["variant"]
        raw = train["variants"][name]["decile_returns"]
        for key in ("K1_desized", "K2_momentum_neutral"):
            rec = score_years(f"{name}_{key}", TRAIN, draws)
            rec["grouping_live"] = any(abs(rec["decile_returns"][d] - float(raw[str(d)] if str(d) in raw else raw[d])) > 1e-9
                                       for d in range(1, 11))
            rec["passes"] = bool(rec["verdict"].startswith("ORDERS") and rec["grouping_live"])
            out[f"{name}_{key}"] = rec
            print(f"{name}_{key:22} train full {_f(rec['monotonicity'])} mid8 "
                  f"{_f(rec['monotonicity_middle_8'])} live {rec['grouping_live']} "
                  f"ties {rec['tie_check_passed']} pass {rec['passes']} | {rec['verdict'][:50]}")
    (OUT / "train_kill.json").write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


def freeze_committed() -> bool:
    rel = FREEZE.relative_to(ROOT.parent)
    log = subprocess.run(["git", "log", "--oneline", "--", str(rel)], cwd=ROOT.parent,
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", str(rel)], cwd=ROOT.parent,
                           capture_output=True, text=True).stdout.strip()
    return bool(log) and not dirty


def phase_holdout(config: dict, draws: int) -> int:
    if not freeze_committed():
        raise SystemExit("REFUSED: docs/BRAIN_A15_TRAIN_FREEZE_V1.md is not committed and clean")
    train = json.loads((OUT / "train.json").read_text())
    kill = json.loads((OUT / "train_kill.json").read_text()) if (OUT / "train_kill.json").exists() else {}
    n_sims = len(list(SIMS.glob("*.json")))
    prior = config["reading"]["multiple_testing"]["prior_simulations_on_account_at_registration"]
    denominator = prior + n_sims
    controls = {}
    for cid in train["controls"]:
        controls[cid] = {"full": score_full(f"control_{cid}", draws),
                         "hold_2023": score_years(f"control_{cid}", (HOLD,), 1)}
    out, pvals = {}, {}
    for name, rec in train["variants"].items():
        if rec["status"] != "scored":
            continue
        full = score_full(name, draws)
        hold = score_years(name, (HOLD,), 1)
        ctl = controls.get(rec["control"])
        beats = None
        if ctl and ctl["full"]["tie_check_passed"]:
            beats = bool(full["monotonicity"] > ctl["full"]["monotonicity"]
                         and full["monotonicity_middle_8"] > ctl["full"]["monotonicity_middle_8"])
        prod = (A.cached(f"{name}_production") or {})
        prows = yearly_rows(prod)
        out[name] = {"hypothesis": rec["hypothesis"], "full": full, "hold_2023": hold,
                     "control_full_beaten": beats,
                     "production_not_evidence": prod.get("is"),
                     "production_2023_not_evidence": prows.get(HOLD),
                     "production_alpha_id": prod.get("alpha_id")}
        pvals[name] = full["permutation_p"]
    fdr = A.bh(pvals)
    verdicts = {}
    for hyp, b in train["best"].items():
        name = b["variant"]
        if not name or name not in out:
            verdicts[hyp] = {"variant": name, "PASS": False, "why": "no scored variant"}
            continue
        o = out[name]
        kills = {k: v["passes"] for k, v in kill.items() if k.startswith(name + "_")}
        p1 = bool(o["full"]["verdict"].startswith("ORDERS") and o["control_full_beaten"]
                  and o["full"]["tie_check_passed"]
                  and o["full"]["permutation_p"] < 0.05 / denominator)
        h = o["hold_2023"]
        p2 = bool(h["monotonicity"] == h["monotonicity"] and h["monotonicity"] > 0
                  and h["top_minus_bottom"] > 0)
        passed = bool(b["passes_train"] and kills and all(kills.values()) and p1 and p2)
        verdicts[hyp] = {"variant": name, "passes_train": b["passes_train"], "kill_tests": kills,
                         "P1_full_window": p1, "P2_2023": p2, "PASS": passed}
    kill_hold = {}
    for key in kill:
        kill_hold[key] = {"full": score_full(key, draws), "hold_2023": score_years(key, (HOLD,), 1)}
    result = {"bonferroni_denominator_final": denominator, "a15_simulations": n_sims,
              "bh_fdr_full_window": fdr, "controls": controls, "variants": out,
              "kill_ladders": kill_hold, "verdicts": verdicts}
    (OUT / "holdout.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    rows = []
    for name, o in out.items():
        prod = o["production_not_evidence"] or {}
        tr = train["variants"][name]
        rows.append({"hypothesis": o["hypothesis"], "variant": name,
                     "frozen_best": any(v["variant"] == name for v in verdicts.values()),
                     "train_full": _f(tr["monotonicity"]), "train_mid8": _f(tr["monotonicity_middle_8"]),
                     "train_tmb": _f(tr["top_minus_bottom"]),
                     "full_full": _f(o["full"]["monotonicity"]), "full_mid8": _f(o["full"]["monotonicity_middle_8"]),
                     "full_tmb": _f(o["full"]["top_minus_bottom"]),
                     "full_verdict": o["full"]["verdict"][:40],
                     "full_perm_p": _f(o["full"]["permutation_p"], 6), "bh_fdr": fdr.get(name),
                     "beats_control_full": o["control_full_beaten"],
                     "hold2023_mono": _f(o["hold_2023"]["monotonicity"]),
                     "hold2023_mid8": _f(o["hold_2023"]["monotonicity_middle_8"]),
                     "hold2023_tmb": _f(o["hold_2023"]["top_minus_bottom"]),
                     "brain_sharpe_NOT_EVIDENCE": prod.get("sharpe"), "brain_fitness_NOT_EVIDENCE": prod.get("fitness"),
                     "brain_turnover_NOT_EVIDENCE": prod.get("turnover"), "brain_returns_NOT_EVIDENCE": prod.get("returns")})
    with (OUT / "holdout_summary.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(json.dumps(r))
    for cid, c in controls.items():
        print(f"control {cid}: full {_f(c['full']['monotonicity'])} / {_f(c['full']['monotonicity_middle_8'])} "
              f"ties {c['full']['tie_check_passed']} | 2023 {_f(c['hold_2023']['monotonicity'])} "
              f"tmb {_f(c['hold_2023']['top_minus_bottom'])}")
    for k, v in kill_hold.items():
        print(f"{k}: full {_f(v['full']['monotonicity'])}/{_f(v['full']['monotonicity_middle_8'])} "
              f"2023 {_f(v['hold_2023']['monotonicity'])} tmb {_f(v['hold_2023']['top_minus_bottom'])}")
    print("VERDICTS", json.dumps(verdicts, indent=1))
    print(f"Bonferroni denominator {denominator} -> bar {0.05 / denominator:.2e}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True, choices=["probes", "ladders", "controls", "train",
                                                           "kill", "trainkill", "holdout"])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--draws", type=int, default=200_000)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    return {"probes": lambda: phase_probes(config, args.workers),
            "ladders": lambda: phase_ladders(config, args.workers, args.only),
            "controls": lambda: phase_controls(config, args.workers),
            "train": lambda: phase_train(config, args.draws),
            "kill": lambda: phase_kill(config, args.workers),
            "trainkill": lambda: phase_trainkill(config, args.draws),
            "holdout": lambda: phase_holdout(config, args.draws)}[args.phase]()


if __name__ == "__main__":
    raise SystemExit(main())
