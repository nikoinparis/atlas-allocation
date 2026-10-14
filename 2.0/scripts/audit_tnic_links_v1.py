#!/usr/bin/env python3
"""Positive control for A19 (Step 355): are the TNIC links real after our mapping?

A19 found that peers' past returns do not predict a firm's next return. That is only a finding
if the links themselves are right. If the gvkey->CIK mapping or the dating were broken, peers
would be random firms and the null would be an implementation artefact. Two checks:

1. Co-movement: peers' return over a month should correlate with the firm's OWN return over the
   SAME month far more than random firms' returns do. Same-window, so this is a diagnostic of the
   links, not a trading signal and not a trial.
2. Face validity: list the nearest TNIC peers of a few well-known firms, with tickers.
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
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

OUTPUT = ROOT / "evidence/tnic_link_audit_v1"
CATALOGUE = a19.ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
SPOT = ["NVDA", "VRT", "AAPL", "XOM", "MRNA", "DAL", "COST"]


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    tnic = a19.load_tnic()
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False)
    ticker = cat.drop_duplicates("cik10").set_index("cik10").symbol

    cols = np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    px = prices.to_numpy()
    dates = prices.index
    month_end = pd.Series(dates, index=dates).groupby([dates.year, dates.month]).last()
    rng = np.random.default_rng(355)
    rows, cache = [], {}
    for when in month_end:
        if when < pd.Timestamp("2012-01-01") or when > pd.Timestamp("2025-06-30"):
            continue
        pos = dates.get_loc(when)
        year = a19.tnic_year_for(when)
        if year not in cache:
            mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
            e = tnic[tnic.year == year]
            c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
            keep = c1.isin(col_pos) & c2.isin(col_pos) & (c1 != c2)
            ed = pd.DataFrame({"i": c1[keep].map(col_pos), "j": c2[keep].map(col_pos), "w": e.score[keep].to_numpy()})
            ed = ed.groupby(["i", "j"], as_index=False).w.max()
            cache[year] = sparse.csr_matrix((ed.w, (ed.i, ed.j)), shape=(len(cols), len(cols)))
        w = cache[year]
        r = px[pos] / px[pos - 21] - 1.0
        ok = np.isfinite(r) & (px[pos] >= 5)
        peer = a19.peer_mean(w, r)
        rand = a19.peer_mean(w, r[rng.permutation(len(cols))])
        groups = a19.sic_as_of(sic, when).reindex(cols).str[:3]
        frame = pd.DataFrame({"g": groups.to_numpy(), "r": np.where(ok, r, np.nan)})
        g = frame.groupby("g").r
        sic3 = ((g.transform("sum") - frame.r) / (g.transform("count") - 1)).where(g.transform("count") > 1).to_numpy()
        rows.append({"date": when,
                     "same_month_ic_tnic": a19.rank_ic(np.where(ok, peer, np.nan), r),
                     "same_month_ic_random_peers": a19.rank_ic(np.where(ok, rand, np.nan), r),
                     "same_month_ic_sic3": a19.rank_ic(np.where(ok, sic3, np.nan), r)})
    co = pd.DataFrame(rows)
    co.to_csv(OUTPUT / "same_month_comovement.csv", index=False)
    summary = co.drop(columns="date").agg(["mean", "std", "min"]).round(4)
    print("same-month rank correlation, firm return vs its peers' return (diagnostic, not a signal):")
    print(summary.to_string())

    spot = {}
    year = 2022                                   # usable July 2023 - June 2024
    mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
    e = tnic[tnic.year == year].copy()
    e["c1"], e["c2"] = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
    inv = {v: k for k, v in ticker.items()}
    for sym in SPOT:
        cik = inv.get(sym)
        sub = e[e.c1 == cik].sort_values("score", ascending=False)
        peers = [f"{ticker.get(c, '?')}({s:.3f})" for c, s in zip(sub.c2, sub.score) if isinstance(c, str)][:15]
        spot[sym] = {"n_peers": int(len(sub)), "in_price_panel": int(sub.c2.isin(col_pos).sum()), "nearest_15": peers}
        print(f"\n{sym} TNIC-{year} peers: {len(sub)} total, {spot[sym]['in_price_panel']} in panel")
        print("  " + ", ".join(peers))
    (OUTPUT / "result.json").write_text(json.dumps({
        "same_month_comovement": summary.to_dict(), "spot_checks_tnic_2022": spot,
        "decisions": int(len(co))}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
