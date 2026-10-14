#!/usr/bin/env python3
"""A19's screen, generalised to any firm-pair network: A21 (VTNIC vertical links) and A19b (ETNIC).

The measurement, controls, placebo and pass rule are imported from or identical to
run_tnic_peer_gap_screen_v1.py. What changes per experiment is the network and how a firm's
partners are chosen from it, both fixed in each experiment's registry before data was downloaded.

    python scripts/run_network_peer_screen_v1.py vtnic
    python scripts/run_network_peer_screen_v1.py etnic
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

EXPERIMENTS = {
    "vtnic": {
        "registry": "config/vtnic_vertical_links_registry_v1.json",
        "zip": "data/vtnic_v1/download/VertNetwork_10gran.zip",
        "cache": "data/vtnic_v1/vtnic10_2009_2021_pairs.csv.gz",
        "years": (2009, 2021),
        "output": "evidence/vtnic_vertical_links_v1",
        "design": ("2012-01-01", "2018-12-31"), "holdout": ("2019-01-01", "2023-06-30"),
        "bar": 0.025,
        "trials": {
            "T1_customers_lead_suppliers_1m": {"direction": "out", "top_n": 10, "non_sic3": False},
            "T2_suppliers_lead_customers_1m": {"direction": "in", "top_n": 10, "non_sic3": False},
        },
    },
    "etnic": {
        "registry": "config/etnic_peer_screen_registry_v1.json",
        "zip": "data/etnic_v1/download/Etnic3_data.zip",
        "cache": "data/etnic_v1/etnic3_2009_2023_pairs.csv.gz",
        "years": (2009, 2023),
        "output": "evidence/etnic_peer_screen_v1",
        "design": ("2012-01-01", "2018-12-31"), "holdout": ("2019-01-01", "2025-06-30"),
        "bar": 0.025,
        "trials": {
            "T1_all_embedding_peers_1m": {"direction": "out", "top_n": None, "non_sic3": False},
            "T2_non_sic3_embedding_peers_1m": {"direction": "out", "top_n": None, "non_sic3": True},
        },
    },
}
PLACEBO_RUNS = 200


def load_pairs(cfg: dict) -> pd.DataFrame:
    cache = ROOT / cfg["cache"]
    if cache.is_file():
        return pd.read_csv(cache)
    a, b = cfg["years"]
    parts = []
    with zipfile.ZipFile(ROOT / cfg["zip"]) as archive:
        name = max(archive.namelist(), key=lambda n: archive.getinfo(n).file_size)
    # The 3.1GB VTNIC member uses a method Python's zipfile cannot read (Deflate64); stream it
    # through the system unzip, which verified the archive (`unzip -t`) before this ran.
    proc = subprocess.Popen(["unzip", "-p", str(ROOT / cfg["zip"]), name], stdout=subprocess.PIPE)
    for chunk in pd.read_csv(proc.stdout, sep="\t", chunksize=5_000_000):
        chunk.columns = ["year", "gvkey1", "gvkey2", "score"]
        chunk = chunk[(chunk.year >= a) & (chunk.year <= b) & (chunk.gvkey1 != chunk.gvkey2)]
        parts.append(chunk.dropna(subset=["score"]))
    if proc.wait() != 0:
        raise RuntimeError("unzip failed")
    pairs = pd.concat(parts, ignore_index=True)
    pairs.to_csv(cache, index=False)
    return pairs


def weights_for(edges: pd.DataFrame, trial: dict, sic3: np.ndarray, n: int) -> sparse.csr_matrix:
    """edges: i -> j with weight w in panel positions. Row = focal firm, column = partner."""
    e = edges if trial["direction"] == "out" else edges.rename(columns={"i": "j", "j": "i"})
    if trial["non_sic3"]:
        s_i, s_j = pd.Series(sic3[e.i.to_numpy()]), pd.Series(sic3[e.j.to_numpy()])
        e = e[(s_i.notna() & s_j.notna() & (s_i != s_j)).to_numpy()]
    if trial["top_n"]:
        e = e.sort_values("w", ascending=False).groupby("i").head(trial["top_n"])
    return sparse.csr_matrix((e.w, (e.i, e.j)), shape=(n, n))


def main(which: str) -> int:
    cfg = EXPERIMENTS[which]
    registry = json.loads((ROOT / cfg["registry"]).read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261014 + len(which))
    out = ROOT / cfg["output"]
    out.mkdir(parents=True, exist_ok=True)
    design, holdout, bar = cfg["design"], cfg["holdout"], cfg["bar"]

    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns)
    pairs = load_pairs(cfg)
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    print(f"{which}: pairs {len(pairs):,} years {pairs.year.min()}-{pairs.year.max()}")

    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    n, px = len(cols), prices.to_numpy()
    month_end = pd.Series(dates, index=dates).groupby([dates.year, dates.month]).last()
    decisions = [d for d in month_end if pd.Timestamp(design[0]) <= d <= pd.Timestamp(holdout[1])]
    cache, rows, coverage, comove = {}, [], [], []
    placebo = {t: [] for t in cfg["trials"]}
    for when in decisions:
        pos = dates.get_loc(when)
        if pos < 252 or pos + 1 + 21 >= len(dates):
            continue
        year = a19.tnic_year_for(when)
        if year not in cache:
            mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
            e = pairs[pairs.year == year]
            c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
            keep = c1.isin(col_pos) & c2.isin(col_pos) & (c1 != c2)
            ed = pd.DataFrame({"i": c1[keep].map(col_pos).to_numpy(), "j": c2[keep].map(col_pos).to_numpy(),
                               "w": e.score[keep].to_numpy()})
            cache[year] = ed.groupby(["i", "j"], as_index=False).w.max()
        edges = cache[year]
        groups = a19.sic_as_of(sic, when).reindex(cols)
        sic3 = groups.str[:3].to_numpy(dtype=object)
        sic2 = groups.str[:2].to_numpy(dtype=object)
        p0 = px[pos]
        r21 = p0 / px[pos - 21] - 1.0
        mom = px[pos - 21] / px[pos - 252] - 1.0
        fwd = px[pos + 22] / px[pos + 1] - 1.0
        dpos = dollar.index.get_indexer([when], method="pad")[0]
        dv = dollar.iloc[dpos].to_numpy() if dpos >= 0 else np.full(n, np.nan)
        universe = (np.isfinite(p0) & (p0 >= a19.MIN_PRICE) & (dv >= a19.MIN_DOLLAR_VOLUME)
                    & np.isfinite(r21) & np.isfinite(mom) & pd.notna(groups).to_numpy())
        frame = pd.DataFrame({"sic2": sic2, "r": np.where(universe, r21, np.nan)})
        g = frame.groupby("sic2").r
        sic2_ret = ((g.transform("sum") - frame.r) / (g.transform("count") - 1)).where(g.transform("count") > 1).to_numpy()
        controls = np.column_stack([r21, mom, sic2_ret])
        in_design = pd.Timestamp(design[0]) <= when <= pd.Timestamp(design[1])
        record = {"date": when, "cik": cols, "sic2": sic2}
        cov = {"date": when, "universe": int(universe.sum())}
        cm = {"date": when}
        for name, trial in cfg["trials"].items():
            w = weights_for(edges, trial, sic3, n)
            has = np.asarray((w > 0).sum(axis=1)).ravel() > 0
            cov[name] = int((universe & has).sum())
            raw = np.where(universe, a19.peer_mean(w, r21), np.nan)
            # Positive control: same-window co-movement, real partners vs random ones.
            cm[name + "_same_month"] = a19.rank_ic(raw, np.where(universe, r21, np.nan))
            cm[name + "_same_month_random"] = a19.rank_ic(
                np.where(universe, a19.peer_mean(w, r21[rng.permutation(n)]), np.nan), np.where(universe, r21, np.nan))
            record[name] = {"raw": raw, "resid": a19.residualise(raw, controls), "fwd": fwd}
            if in_design:
                draws = []
                for _ in range(PLACEBO_RUNS):
                    pr = np.where(universe, a19.peer_mean(w, r21[rng.permutation(n)]), np.nan)
                    draws.append(a19.rank_ic(a19.residualise(pr, controls), fwd))
                placebo[name].append(draws)
        rows.append(record)
        coverage.append(cov)
        comove.append(cm)

    coverage = pd.DataFrame(coverage)
    comove = pd.DataFrame(comove)
    coverage.to_csv(out / "coverage.csv", index=False)
    comove.to_csv(out / "same_month_comovement.csv", index=False)
    print("\npositive control, mean same-month rank correlation (real partners vs random):")
    print(comove.drop(columns="date").mean().round(4).to_string())
    share = {t: (coverage[t] / coverage.universe).groupby(coverage.date.dt.year).mean() for t in cfg["trials"]}
    print("\ncoverage (universe issuers with >= 1 partner), by year:")
    print(pd.DataFrame(share).round(3).to_string())
    gate = all(((s[(s.index >= 2012) & (s.index <= 2018)]) >= a19.COVERAGE_GATE).all() for s in share.values())
    print(f"coverage gate: {'PASS' if gate else 'FAIL'}")

    a19.BAR = bar
    design_rows = [r for r in rows if pd.Timestamp(design[0]) <= r["date"] <= pd.Timestamp(design[1])]
    results = []
    for k, name in enumerate(cfg["trials"]):
        daily = a19.per_decision(rows, name)
        res = {"trial": name,
               "design": a19.summarise(a19.window(daily, *design), 6, 21, rng, seed=k),
               "holdout": a19.summarise(a19.window(daily, *holdout), 6, 21, rng, seed=100 + k),
               "regimes": {lab: a19.summarise(a19.window(daily, a, b), 6, 21, rng, seed=200 + k)
                           for lab, (a, b) in a19.REGIMES.items()}}
        p = np.nanmean(np.array(placebo[name]), axis=0)
        res["placebo_network"] = {"mean": float(p.mean()), "p95": float(np.percentile(p, 95))}
        res["leave_out"] = a19.leave_out(rows, name, design_rows)
        d, h = res["design"], res["holdout"]
        res["criteria"] = {
            "coverage_gate": gate,
            "design_ic_positive_p_below_bar": d["mean_ic"] > 0 and d["bootstrap_p"] < bar,
            "design_ladder_clears_positive": d["clears"] and d["monotonicity"] > 0,
            "design_ladder_clears_calibrated": bool(d["clears_calibrated"]) and d["monotonicity"] > 0,
            "design_ic_above_placebo_network_p95": d["mean_ic"] > res["placebo_network"]["p95"],
            "design_leave_outs_positive": res["leave_out"]["min_leave_one_sic2_out_ic"] > 0
                                          and res["leave_out"]["ic_without_top10_names"] > 0,
            "holdout_ic_positive_and_ladder_clears": h["mean_ic"] > 0 and h["clears"] and h["monotonicity"] > 0,
        }
        res["screen_passes"] = all(res["criteria"].values())
        results.append(res)
        print(f"\n== {name}")
        for label in ("design", "holdout"):
            s = res[label]
            print(f"  {label:8s} n={s['decisions']:3d} names~{s['median_names']:.0f}  IC {s['mean_ic']:+.4f} t {s['t_stat']:+.2f} "
                  f"p {s['bootstrap_p']:.4f}  spread/yr {s['decile_spread_annualised']:+.2%}  mono {s['monotonicity']:+.3f} "
                  f"mid8 {s['monotonicity_middle_8']:+.3f} calib p {s['calibrated']['p']:.3f}")
        for lab, s in res["regimes"].items():
            if not s.get("inconclusive"):
                print(f"    {lab:12s} n={s['decisions']:3d} IC {s['mean_ic']:+.4f} p {s['bootstrap_p']:.3f} "
                      f"spread/yr {s['decile_spread_annualised']:+.2%} mono {s['monotonicity']:+.3f} mid8 {s['monotonicity_middle_8']:+.3f}")
        lo = res["leave_out"]
        print(f"  placebo network mean {res['placebo_network']['mean']:+.4f} p95 {res['placebo_network']['p95']:+.4f}; "
              f"leave-one-SIC2-out min {lo['min_leave_one_sic2_out_ic']:+.4f}; without top-10 {lo['ic_without_top10_names']:+.4f}")
        for c, v in res["criteria"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {c}")
        print(f"  SCREEN {'PASSES' if res['screen_passes'] else 'FAILS'}")

    (out / "result.json").write_text(json.dumps({
        "registry": cfg["registry"], "coverage_gate": gate, "positive_control": comove.drop(columns="date").mean().to_dict(),
        "results": results, "any_trial_passes": any(r["screen_passes"] for r in results),
        "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
