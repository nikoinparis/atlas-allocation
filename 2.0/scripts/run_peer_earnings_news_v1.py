#!/usr/bin/env python3
"""Queue item A20: do linked firms' earnings surprises predict a firm's next quarter?

Pre-registered in config/peer_earnings_news_registry_v1.json, declared underpowered in advance
(27 quarterly design decisions). T1 uses TNIC product peers (A19's network), T2 the ten nearest
VTNIC customers (A21's). Signals are residualised on the firm's OWN surprise, so what is ranked
is news that reached the firm's peers, not the firm itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_network_peer_screen_v1 as net  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/peer_earnings_news_registry_v1.json"
SUE = ROOT / "evidence/extended_sue_panel_v1/sue_panel.csv.gz"
OUTPUT = ROOT / "evidence/peer_earnings_news_v1"
BAR, PLACEBO_RUNS, HORIZON = 0.025, 200, 63
DESIGN = ("2012-04-01", "2018-10-01")
HOLDOUT = {"T1_product_peers_sue_3m": ("2019-01-01", "2025-04-01"),
           "T2_customers_sue_3m": ("2019-01-01", "2023-04-01")}


def network_edges(pairs, links, year, col_pos):
    mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
    e = pairs[pairs.year == year]
    c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
    keep = c1.isin(col_pos) & c2.isin(col_pos) & (c1 != c2)
    ed = pd.DataFrame({"i": c1[keep].map(col_pos).to_numpy(), "j": c2[keep].map(col_pos).to_numpy(),
                       "w": e.score[keep].to_numpy()})
    return ed.groupby(["i", "j"], as_index=False).w.max()


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261020)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns)
    tnic = a19.load_tnic()
    vtnic = net.load_pairs(net.EXPERIMENTS["vtnic"])
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    sue = pd.read_csv(SUE, parse_dates=["decision_at"])
    sue["cik10"] = sue.cik10.astype("int64").astype(str).str.zfill(10)

    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    n, px = len(cols), prices.to_numpy()
    rows, comove = [], []
    placebo = {"T1_product_peers_sue_3m": [], "T2_customers_sue_3m": []}
    for decision, panel in sue.groupby("decision_at"):
        if decision < pd.Timestamp(DESIGN[0]) or decision > pd.Timestamp(HOLDOUT["T1_product_peers_sue_3m"][1]):
            continue
        pos = dates.searchsorted(decision) - 1                   # last trading day BEFORE the decision
        if pos < 252 or pos + 1 + HORIZON >= len(dates):
            continue
        when = dates[pos]
        year = a19.tnic_year_for(when)
        s = panel.set_index("cik10").standardized_unexpected_earnings.reindex(cols).to_numpy(dtype=float)
        groups = a19.sic_as_of(sic, when).reindex(cols)
        sic2 = groups.str[:2].to_numpy(dtype=object)
        p0 = px[pos]
        r63 = p0 / px[pos - 63] - 1.0
        mom = px[pos - 21] / px[pos - 252] - 1.0
        fwd = px[pos + 1 + HORIZON] / px[pos + 1] - 1.0
        dpos = dollar.index.get_indexer([when], method="pad")[0]
        dv = dollar.iloc[dpos].to_numpy() if dpos >= 0 else np.full(n, np.nan)
        universe = (np.isfinite(p0) & (p0 >= a19.MIN_PRICE) & (dv >= a19.MIN_DOLLAR_VOLUME) & np.isfinite(s)
                    & np.isfinite(r63) & np.isfinite(mom) & pd.notna(groups).to_numpy())
        frame = pd.DataFrame({"sic2": sic2, "r": np.where(universe, r63, np.nan)})
        g = frame.groupby("sic2").r
        sic2_ret = ((g.transform("sum") - frame.r) / (g.transform("count") - 1)).where(g.transform("count") > 1).to_numpy()
        controls = np.column_stack([s, r63, mom, sic2_ret])

        weights = {"T1_product_peers_sue_3m": None, "T2_customers_sue_3m": None}
        te = network_edges(tnic, links, year, col_pos)
        weights["T1_product_peers_sue_3m"] = sparse.csr_matrix((te.w, (te.i, te.j)), shape=(n, n))
        if year <= 2021:
            # A21 v2's selected construction (lift), per the A20 amendment made before this ran.
            ve = net.add_lift_and_hubs(network_edges(vtnic, links, year, col_pos))
            weights["T2_customers_sue_3m"] = net.weights_for(ve, {"direction": "out", "top_n": 10, "score": "lift"},
                                                             None, n)
        record = {"date": when, "cik": cols, "sic2": sic2}
        cm = {"date": when, "universe": int(universe.sum())}
        for name, w in weights.items():
            if w is None:
                continue
            raw = np.where(universe, a19.peer_mean(w, s), np.nan)
            cm[name + "_same_quarter"] = a19.rank_ic(raw, np.where(universe, s, np.nan))
            cm[name + "_same_quarter_random"] = a19.rank_ic(
                np.where(universe, a19.peer_mean(w, s[rng.permutation(n)]), np.nan), np.where(universe, s, np.nan))
            cm[name + "_names"] = int(np.isfinite(raw).sum())
            record[name] = {"raw": raw, "resid": a19.residualise(raw, controls), "fwd": fwd}
            if decision <= pd.Timestamp(DESIGN[1]):
                draws = []
                for _ in range(PLACEBO_RUNS):
                    pr = np.where(universe, a19.peer_mean(w, s[rng.permutation(n)]), np.nan)
                    draws.append(a19.rank_ic(a19.residualise(pr, controls), fwd))
                placebo[name].append(draws)
        rows.append(record)
        comove.append(cm)

    comove = pd.DataFrame(comove)
    comove.to_csv(OUTPUT / "same_quarter_comovement.csv", index=False)
    print("positive control, mean same-quarter rank correlation of peers' SUE with own SUE:")
    print(comove.drop(columns="date").mean().round(4).to_string())

    a19.BAR = BAR
    results = []
    for k, name in enumerate(placebo):
        trial_rows = [r for r in rows if name in r]
        daily = a19.per_decision(trial_rows, name)
        design = a19.window(daily, DESIGN[0], "2018-12-31")
        hold = a19.window(daily, *HOLDOUT[name])
        res = {"trial": name, "design": a19.summarise(design, 2, HORIZON, rng, seed=k),
               "holdout": a19.summarise(hold, 2, HORIZON, rng, seed=10 + k)}
        p = np.nanmean(np.array(placebo[name]), axis=0)
        res["placebo_network"] = {"mean": float(p.mean()), "p95": float(np.percentile(p, 95))}
        design_rows = [r for r in trial_rows if r["date"] <= pd.Timestamp("2018-12-31")]
        res["leave_out"] = a19.leave_out(trial_rows, name, design_rows)
        d, h = res["design"], res["holdout"]
        res["criteria"] = {
            "design_ic_positive_p_below_bar": d["mean_ic"] > 0 and d["bootstrap_p"] < BAR,
            "design_ladder_clears_positive": d["clears"] and d["monotonicity"] > 0,
            "design_ladder_clears_calibrated": bool(d["clears_calibrated"]) and d["monotonicity"] > 0,
            "design_ic_above_placebo_network_p95": d["mean_ic"] > res["placebo_network"]["p95"],
            "design_leave_outs_positive": res["leave_out"]["min_leave_one_sic2_out_ic"] > 0
                                          and res["leave_out"]["ic_without_top10_names"] > 0,
            "holdout_ic_positive_and_ladder_clears": (not h.get("inconclusive")) and h["mean_ic"] > 0
                                                     and h["clears"] and h["monotonicity"] > 0,
        }
        res["screen_passes"] = all(res["criteria"].values())
        results.append(res)
        print(f"\n== {name}")
        for label in ("design", "holdout"):
            s_ = res[label]
            if s_.get("inconclusive"):
                print(f"  {label}: inconclusive ({s_['decisions']} decisions)"); continue
            print(f"  {label:8s} n={s_['decisions']:3d} names~{s_['median_names']:.0f}  IC {s_['mean_ic']:+.4f} t {s_['t_stat']:+.2f} "
                  f"p {s_['bootstrap_p']:.4f}  spread/yr {s_['decile_spread_annualised']:+.2%}  mono {s_['monotonicity']:+.3f} "
                  f"mid8 {s_['monotonicity_middle_8']:+.3f} calib p {s_['calibrated']['p']:.3f}")
        lo = res["leave_out"]
        print(f"  placebo network mean {res['placebo_network']['mean']:+.4f} p95 {res['placebo_network']['p95']:+.4f}; "
              f"leave-one-SIC2-out min {lo['min_leave_one_sic2_out_ic']:+.4f}; without top-10 {lo['ic_without_top10_names']:+.4f}")
        for c, v in res["criteria"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {c}")
        print(f"  SCREEN {'PASSES' if res['screen_passes'] else 'FAILS'}")

    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "positive_control": comove.drop(columns="date").mean().to_dict(),
        "results": results, "any_trial_passes": any(r["screen_passes"] for r in results),
        "underpowered_by_design": True, "live_trading_enabled": False,
        "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
