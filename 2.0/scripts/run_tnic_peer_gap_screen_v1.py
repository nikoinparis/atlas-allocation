#!/usr/bin/env python3
"""Queue item A19: do a firm's 10-K product peers lead its returns?

Pre-registered in config/tnic_peer_gap_registry_v1.json (committed before any TNIC or link data
was downloaded). A18's theme-diffusion idea rests on one mechanism: news reaches the obvious
firms first and their less obvious, economically linked peers later. This is its cheapest
direct test, on the Hoberg-Phillips TNIC-3 product-similarity network.

Four trials, each a similarity-weighted peer return residualised on the firm's own 1-month
return, own 12-1 momentum and its SIC2 industry return. Design window 2012-2018, holdout
2019-2025H1. CLAUDE.md section 2 fixes the order: skill screen first, a book only if a trial
passes every criterion.

Note from the TNIC readme, read before running: TNIC is purged of vertical (input-output)
relationships. This tests spillover between firms selling similar products, not
supplier-customer chains.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import decile_shape as ds  # noqa: E402
from run_stat_arb_residual_screen_v1 import load_daily, load_sic, sic_as_of  # noqa: E402

REGISTRY = ROOT / "config/tnic_peer_gap_registry_v1.json"
TNIC_ZIP = ROOT / "data/tnic_v1/download/tnic3_data.zip"
TNIC_CACHE = ROOT / "data/tnic_v1/tnic3_2009_2023_pairs.csv.gz"
LINKS = ROOT / "data/farr_gvkey_ciks_v1/gvkey_ciks.csv.gz"
VOLUME = ROOT / "data/us_daily_volume_v1"
OUTPUT = ROOT / "evidence/tnic_peer_gap_screen_v1"

MIN_PRICE, MIN_DOLLAR_VOLUME = 5.0, 5_000_000.0
FIRST_YEAR, LAST_YEAR = 2009, 2023
DESIGN = ("2012-01-01", "2018-12-31")
HOLDOUT = ("2019-01-01", "2025-06-30")
REGIMES = {"2012-2019": ("2012-01-01", "2019-12-31"), "2020": ("2020-01-01", "2020-12-31"),
           "2021-2022": ("2021-01-01", "2022-12-31"), "2023-2025H1": ("2023-01-01", "2025-06-30")}
BAR = 0.0125
PLACEBO_RUNS = 200
COVERAGE_GATE = 0.70
TRIALS = {
    "T1_all_peers_1m": {"peers": "all", "lookback": 21, "gap": False, "horizon": 21, "block": 6},
    "T2_non_sic3_peers_1m": {"peers": "non_sic3", "lookback": 21, "gap": False, "horizon": 21, "block": 6},
    "T3_gap_6m": {"peers": "all", "lookback": 126, "gap": True, "horizon": 21, "block": 6},
    "T4_non_sic3_peers_3m": {"peers": "non_sic3", "lookback": 21, "gap": False, "horizon": 63, "block": 9},
}


# ------------------------------------------------------------------------------------------
# Data
# ------------------------------------------------------------------------------------------

def load_tnic() -> pd.DataFrame:
    if TNIC_CACHE.is_file():
        return pd.read_csv(TNIC_CACHE)
    parts = []
    with zipfile.ZipFile(TNIC_ZIP) as archive, archive.open("tnic3_data.txt") as handle:
        for chunk in pd.read_csv(handle, sep="\t", chunksize=5_000_000):
            chunk = chunk[(chunk.year >= FIRST_YEAR) & (chunk.year <= LAST_YEAR)
                          & (chunk.gvkey1 != chunk.gvkey2)]           # readme note 2: drop self
            parts.append(chunk)
    tnic = pd.concat(parts, ignore_index=True)
    tnic.to_csv(TNIC_CACHE, index=False)
    return tnic


def gvkey_to_cik(links: pd.DataFrame, when: pd.Timestamp) -> pd.Series:
    """One CIK per gvkey as of `when`: the link whose interval contains it, else the nearest.
    gvkeys that resolve to more than one CIK at once are dropped (registry)."""
    links = links.copy()
    inside = (links.first_date <= when) & (links.last_date >= when)
    links["distance"] = np.where(inside, 0,
                                 np.minimum((links.first_date - when).abs().dt.days,
                                            (links.last_date - when).abs().dt.days))
    best = links[links.distance == links.groupby("gvkey").distance.transform("min")]
    best = best.drop_duplicates(["gvkey", "cik10"])
    ambiguous = best.gvkey.duplicated(keep=False)
    best = best[~ambiguous]
    return best.set_index("gvkey").cik10


def tnic_year_for(when: pd.Timestamp) -> int:
    """TNIC year Y is usable July 1 Y+1 to June 30 Y+2."""
    return when.year - 1 if when.month >= 7 else when.year - 2


def load_dollar_volume(columns) -> pd.DataFrame:
    close = pd.read_csv(VOLUME / "daily_close.csv.gz", index_col=0, parse_dates=True)
    volume = pd.read_csv(VOLUME / "daily_volume.csv.gz", index_col=0, parse_dates=True)
    dollar = (close * volume).rolling(63, min_periods=40).median()
    dollar.columns = [str(c).zfill(10) for c in dollar.columns]
    return dollar.reindex(columns=columns)


# ------------------------------------------------------------------------------------------
# Signals
# ------------------------------------------------------------------------------------------

def peer_mean(weights: sparse.csr_matrix, values: np.ndarray) -> np.ndarray:
    """Weighted mean of `values` over each row's peers that have a value."""
    mask = np.isfinite(values)
    filled = np.where(mask, values, 0.0)
    num = weights @ filled
    den = weights @ mask.astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def residualise(y: np.ndarray, controls: np.ndarray) -> np.ndarray:
    ok = np.isfinite(y) & np.isfinite(controls).all(axis=1)
    out = np.full_like(y, np.nan)
    if ok.sum() < 50:
        return out
    x = np.column_stack([np.ones(ok.sum()), controls[ok]])
    beta, *_ = np.linalg.lstsq(x, y[ok], rcond=None)
    out[ok] = y[ok] - x @ beta
    return out


def rank_ic(score: np.ndarray, target: np.ndarray) -> float:
    ok = np.isfinite(score) & np.isfinite(target)
    if ok.sum() < 50:
        return float("nan")
    return float(pd.Series(score[ok]).rank().corr(pd.Series(target[ok]).rank()))


def decile_means(score: np.ndarray, target: np.ndarray) -> np.ndarray | None:
    ok = np.isfinite(score) & np.isfinite(target)
    if ok.sum() < 100:
        return None
    decile = pd.qcut(pd.Series(score[ok]).rank(method="first"), 10, labels=False).to_numpy()
    return pd.Series(target[ok]).groupby(decile).mean().reindex(range(10)).to_numpy()


def build(prices, dollar, sic, tnic, links, rng, with_placebo: bool = True):
    dates = prices.index
    cols = np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    month_end = pd.Series(dates, index=dates).groupby([dates.year, dates.month]).last()
    decisions = [d for d in month_end if pd.Timestamp(DESIGN[0]) <= d <= pd.Timestamp(HOLDOUT[1])]
    px = prices.to_numpy()

    network_cache: dict[int, tuple] = {}
    rows, coverage_rows, placebo_ics = [], [], {t: [] for t in TRIALS}
    for when in decisions:
        pos = dates.get_loc(when)
        if pos < 252 or pos + 1 + 63 >= len(dates):
            continue
        year = tnic_year_for(when)
        if year not in network_cache:
            usable = pd.Timestamp(f"{year + 1}-07-01")
            mapping = gvkey_to_cik(links, usable)
            edges = tnic[tnic.year == year]
            c1 = edges.gvkey1.map(mapping)
            c2 = edges.gvkey2.map(mapping)
            keep = c1.isin(col_pos) & c2.isin(col_pos) & (c1 != c2)
            e = pd.DataFrame({"i": c1[keep].map(col_pos), "j": c2[keep].map(col_pos),
                              "w": edges.score[keep].to_numpy()})
            e = e.groupby(["i", "j"], as_index=False).w.max()
            network_cache[year] = (e, int(edges.gvkey1.nunique()), int(mapping.size))
        edges, tnic_firms, mapped = network_cache[year]

        groups = sic_as_of(sic, when).reindex(cols)
        sic3 = groups.str[:3].to_numpy(dtype=object)
        sic2 = groups.str[:2].to_numpy(dtype=object)
        p0 = px[pos]
        r21 = p0 / px[pos - 21] - 1.0
        r126 = p0 / px[pos - 126] - 1.0
        mom = px[pos - 21] / px[pos - 252] - 1.0
        fwd = {h: px[pos + 1 + h] / px[pos + 1] - 1.0 for h in (21, 63)}
        dv_pos = dollar.index.get_indexer([when], method="pad")[0]
        dv = dollar.iloc[dv_pos].to_numpy() if dv_pos >= 0 else np.full(len(cols), np.nan)

        universe = (np.isfinite(p0) & (p0 >= MIN_PRICE) & (dv >= MIN_DOLLAR_VOLUME)
                    & np.isfinite(r21) & np.isfinite(r126) & np.isfinite(mom)
                    & pd.notna(groups).to_numpy())

        # Leave-self-out SIC2 21-day return over the eligible universe.
        frame = pd.DataFrame({"sic2": sic2, "r": np.where(universe, r21, np.nan)})
        g = frame.groupby("sic2").r
        total, count = g.transform("sum"), g.transform("count")
        sic2_ret = ((total - frame.r) / (count - 1)).where(count > 1).to_numpy()
        controls = np.column_stack([r21, mom, sic2_ret])

        n = len(cols)
        w_all = sparse.csr_matrix((edges.w, (edges.i, edges.j)), shape=(n, n))
        s_i, s_j = pd.Series(sic3[edges.i]), pd.Series(sic3[edges.j])
        diff = (s_i.notna() & s_j.notna() & (s_i != s_j)).to_numpy()   # unknown SIC3 is not "different"
        e2 = edges[diff]
        w_non = sparse.csr_matrix((e2.w, (e2.i, e2.j)), shape=(n, n))

        has_peer = np.asarray((w_all > 0).sum(axis=1)).ravel() > 0
        coverage_rows.append({"date": when, "universe": int(universe.sum()),
                              "with_tnic_peer": int((universe & has_peer).sum()),
                              "tnic_year": year, "tnic_firms": tnic_firms,
                              "gvkeys_mapped": mapped, "edges_in_panel": int(len(edges))})

        # SIC3 comparator (not a trial): equal-weight leave-self-out over all panel firms.
        cf = pd.DataFrame({"sic3": sic3, "r": r21})
        cg = cf.groupby("sic3").r
        ct, cc = cg.transform("sum"), cg.transform("count")
        sic3_peer = ((ct - cf.r.fillna(0)) / (cc - cf.r.notna().astype(int))).where(cc > 1).to_numpy()

        def raw_signal(trial: dict, perm=None) -> np.ndarray:
            weights = w_all if trial["peers"] == "all" else w_non
            look = r21 if trial["lookback"] == 21 else r126
            values = look if perm is None else look[perm]
            s = peer_mean(weights, values)
            return s - r126 if trial["gap"] else s

        record = {"date": when, "universe": universe}
        for name, trial in TRIALS.items():
            raw = raw_signal(trial)
            raw = np.where(universe, raw, np.nan)
            resid = residualise(raw, controls)
            record[name] = {"raw": raw, "resid": resid, "fwd": fwd[trial["horizon"]]}
            in_design = pd.Timestamp(DESIGN[0]) <= when <= pd.Timestamp(DESIGN[1])
            if in_design and with_placebo:
                draws = []
                for _ in range(PLACEBO_RUNS):
                    perm = rng.permutation(n)
                    pr = np.where(universe, raw_signal(trial, perm), np.nan)
                    draws.append(rank_ic(residualise(pr, controls), fwd[trial["horizon"]]))
                placebo_ics[name].append(draws)
        comp = np.where(universe, sic3_peer, np.nan)
        record["comparator_sic3_1m"] = {"raw": comp, "resid": residualise(comp, controls), "fwd": fwd[21]}
        record["sic2"] = sic2
        record["cik"] = cols
        rows.append(record)
    return rows, pd.DataFrame(coverage_rows), {k: np.array(v) for k, v in placebo_ics.items()}


# ------------------------------------------------------------------------------------------
# Measurement
# ------------------------------------------------------------------------------------------

def per_decision(rows, name: str, exclude=None) -> pd.DataFrame:
    out = []
    for r in rows:
        d = r[name]
        keep = np.isfinite(d["resid"])
        if exclude is not None:
            keep &= ~exclude(r)
        score, target = np.where(keep, d["resid"], np.nan), d["fwd"]
        ladder = decile_means(score, target)
        out.append({"date": r["date"], "n": int(np.isfinite(score).sum()), "ic": rank_ic(score, target),
                    "ladder": ladder,
                    "zero_share": float(np.mean(d["raw"][np.isfinite(d["raw"])] == 0))
                    if np.isfinite(d["raw"]).any() else float("nan")})
    return pd.DataFrame(out).dropna(subset=["ic"])


def bootstrap_p(ics: np.ndarray, block: int, rng) -> float:
    mean = ics.mean()
    draws = np.empty(4000)
    for k in range(4000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws[k] = sample.mean() - mean
    return float((np.abs(draws) >= abs(mean)).mean())


def summarise(daily: pd.DataFrame, block: int, horizon: int, rng, seed: int) -> dict:
    if len(daily) < 12:
        return {"decisions": int(len(daily)), "inconclusive": True}
    ics = daily.ic.to_numpy()
    ladders = np.vstack([l for l in daily.ladder if l is not None])
    avg = pd.Series(ladders.mean(axis=0), index=pd.RangeIndex(10))
    shape = ds.shape(avg)
    cal = ds.placebo_test(ladders, seed=seed)
    per_year = 252.0 / horizon
    return {"decisions": int(len(daily)), "median_names": float(daily.n.median()),
            "mean_ic": float(ics.mean()), "t_stat": float(ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics)))),
            "bootstrap_p": bootstrap_p(ics, block, rng),
            "decile_spread_per_period": float(avg.iloc[-1] - avg.iloc[0]),
            "decile_spread_annualised": float((1 + avg.iloc[-1] - avg.iloc[0]) ** per_year - 1),
            "ladder": [float(x) for x in avg],
            "monotonicity": shape["monotonicity"], "monotonicity_middle_8": shape["monotonicity_middle_8"],
            "extremes_share_of_spread": shape["extremes_share_of_spread"],
            "clears": bool(ds.clears(shape["monotonicity"], shape["monotonicity_middle_8"])),
            "verdict": ds.verdict(shape["monotonicity"], shape["monotonicity_middle_8"]),
            "calibrated": cal, "clears_calibrated": ds.clears_calibrated(cal, alpha=BAR),
            "zero_share": float(daily.zero_share.mean())}


def window(daily: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    return daily[(daily.date >= a) & (daily.date <= b)]


def leave_out(rows, name: str, design_rows) -> dict:
    sic2s = sorted({s for r in design_rows for s in r["sic2"][np.isfinite(r[name]["resid"])] if isinstance(s, str)})
    by_group = {}
    for code in sic2s:
        d = per_decision(design_rows, name, exclude=lambda r, c=code: r["sic2"] == c)
        by_group[code] = float(d.ic.mean())
    parts = []
    for r in design_rows:
        d = r[name]
        ok = np.isfinite(d["resid"]) & np.isfinite(d["fwd"])
        if ok.sum() < 50:
            continue
        zs = pd.Series(d["resid"][ok]).rank()
        zf = pd.Series(d["fwd"][ok]).rank()
        zs, zf = (zs - zs.mean()) / zs.std(), (zf - zf.mean()) / zf.std()
        parts.append(pd.Series((zs * zf).to_numpy() / ok.sum(), index=r["cik"][ok]))
    contribution = pd.concat(parts).groupby(level=0).sum().sort_values(ascending=False)
    top = set(contribution.index[:10])
    d = per_decision(design_rows, name, exclude=lambda r: np.isin(r["cik"], list(top)))
    worst = min(by_group, key=by_group.get)
    return {"min_leave_one_sic2_out_ic": by_group[worst], "worst_sic2_removed": worst,
            "ic_without_top10_names": float(d.ic.mean()), "top10_names": sorted(top)}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261014)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    prices = load_daily()
    sic = load_sic()
    dollar = load_dollar_volume(prices.columns)
    tnic = load_tnic()
    links = pd.read_csv(LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    print(f"prices {prices.shape[1]} issuers {prices.index[0].date()}..{prices.index[-1].date()}; "
          f"TNIC rows {len(tnic):,} years {tnic.year.min()}-{tnic.year.max()}; links {len(links):,}")

    rows, coverage, placebo = build(prices, dollar, sic, tnic, links, rng)
    coverage["share"] = coverage.with_tnic_peer / coverage.universe
    coverage.to_csv(OUTPUT / "coverage.csv", index=False)
    by_year = coverage.groupby(coverage.date.dt.year).share.mean()
    print("\ncoverage (universe issuers with >=1 TNIC peer in the panel), by year:")
    print(by_year.round(3).to_string())
    design_years = by_year[(by_year.index >= 2012) & (by_year.index <= 2018)]
    gate_ok = bool((design_years >= COVERAGE_GATE).all())
    print(f"coverage gate (>= {COVERAGE_GATE:.0%} every design year): {'PASS' if gate_ok else 'FAIL'}")
    if not gate_ok:
        (OUTPUT / "result.json").write_text(json.dumps({
            "registry": str(REGISTRY.relative_to(ROOT)), "coverage_gate": "FAIL",
            "coverage_by_year": by_year.to_dict(), "verdict": "inconclusive by the registry's own rule",
            "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
        return 0

    design_rows = [r for r in rows if pd.Timestamp(DESIGN[0]) <= r["date"] <= pd.Timestamp(DESIGN[1])]
    results = []
    for k, (name, trial) in enumerate(list(TRIALS.items()) + [("comparator_sic3_1m",
                                                                {"horizon": 21, "block": 6})]):
        daily = per_decision(rows, name)
        block, horizon = trial["block"], trial["horizon"]
        res = {"trial": name, "is_trial": name in TRIALS,
               "design": summarise(window(daily, *DESIGN), block, horizon, rng, seed=k),
               "holdout": summarise(window(daily, *HOLDOUT), block, horizon, rng, seed=100 + k),
               "full": summarise(daily, block, horizon, rng, seed=200 + k),
               "regimes": {lab: summarise(window(daily, a, b), block, horizon, rng, seed=300 + k)
                           for lab, (a, b) in REGIMES.items()}}
        raw_daily = daily.copy()
        if name in TRIALS:
            plac = placebo[name]
            plac_mean_ic = np.nanmean(plac, axis=0)                     # one mean IC per draw
            res["placebo_network"] = {"mean": float(np.mean(plac_mean_ic)),
                                      "p95": float(np.percentile(plac_mean_ic, 95))}
            res["leave_out"] = leave_out(rows, name, design_rows)
            d, h = res["design"], res["holdout"]
            res["criteria"] = {
                "design_ic_positive_p_below_bar": d["mean_ic"] > 0 and d["bootstrap_p"] < BAR,
                "design_ladder_clears_positive": d["clears"] and d["monotonicity"] > 0,
                "design_ladder_clears_calibrated": bool(d["clears_calibrated"]) and d["monotonicity"] > 0,
                "design_ic_above_placebo_network_p95": d["mean_ic"] > res["placebo_network"]["p95"],
                "design_leave_outs_positive": res["leave_out"]["min_leave_one_sic2_out_ic"] > 0
                                              and res["leave_out"]["ic_without_top10_names"] > 0,
                "holdout_ic_positive_and_ladder_clears": h["mean_ic"] > 0 and h["clears"] and h["monotonicity"] > 0,
            }
            res["screen_passes"] = all(res["criteria"].values())
        # Raw (un-residualised) IC as a diagnostic only.
        raw_ic = [rank_ic(r[name]["raw"], r[name]["fwd"]) for r in rows]
        res["diagnostic_raw_signal_mean_ic"] = float(np.nanmean(raw_ic))
        results.append(res)

    for r in results:
        print(f"\n== {r['trial']}{'' if r['is_trial'] else '  (comparator, not a trial)'}")
        for label in ("design", "holdout", "full"):
            s = r[label]
            if s.get("inconclusive"):
                print(f"  {label}: inconclusive"); continue
            print(f"  {label:8s} n={s['decisions']:3d} names~{s['median_names']:.0f}  IC {s['mean_ic']:+.4f} "
                  f"t {s['t_stat']:+.2f} p {s['bootstrap_p']:.4f}  spread/yr {s['decile_spread_annualised']:+.2%}  "
                  f"mono {s['monotonicity']:+.3f} mid8 {s['monotonicity_middle_8']:+.3f}  "
                  f"calib p {s['calibrated']['p']:.3f}")
        for lab, s in r["regimes"].items():
            if not s.get("inconclusive"):
                print(f"    {lab:12s} n={s['decisions']:3d} IC {s['mean_ic']:+.4f} p {s['bootstrap_p']:.3f} "
                      f"spread/yr {s['decile_spread_annualised']:+.2%} mono {s['monotonicity']:+.3f} "
                      f"mid8 {s['monotonicity_middle_8']:+.3f}")
        print(f"  raw-signal IC (diagnostic) {r['diagnostic_raw_signal_mean_ic']:+.4f}")
        if r["is_trial"]:
            pn, lo = r["placebo_network"], r["leave_out"]
            print(f"  placebo network: mean {pn['mean']:+.4f} p95 {pn['p95']:+.4f}")
            print(f"  leave-one-SIC2-out min {lo['min_leave_one_sic2_out_ic']:+.4f} (drop {lo['worst_sic2_removed']}), "
                  f"without top-10 names {lo['ic_without_top10_names']:+.4f}")
            for k, v in r["criteria"].items():
                print(f"  [{'PASS' if v else 'FAIL'}] {k}")
            print(f"  SCREEN {'PASSES' if r['screen_passes'] else 'FAILS'}")

    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "coverage_gate": "PASS",
        "coverage_by_year": by_year.to_dict(), "results": results,
        "any_trial_passes": any(r.get("screen_passes") for r in results if r["is_trial"]),
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
