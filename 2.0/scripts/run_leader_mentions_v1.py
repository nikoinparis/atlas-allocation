#!/usr/bin/env python3
"""Queue item A25: do firms that first name a current market leader in their filings outperform?

Pre-registered in config/leader_mentions_registry_v1.json (committed before any mention data was
downloaded). Stages, run in order:

    python scripts/run_leader_mentions_v1.py leaders     # point-in-time leaders and search names
    python scripts/run_leader_mentions_v1.py acquire     # EDGAR full-text search, cached
    python scripts/run_leader_mentions_v1.py precision   # 50 random new mentions with their sentences
    python scripts/run_leader_mentions_v1.py screen      # returns -- only after precision is classified
"""

from __future__ import annotations

import html
import io
import os
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_network_peer_screen_v1 as net  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/leader_mentions_registry_v1.json"
CACHE = ROOT / "data/edgar_fts_leader_mentions_v1"
OUTPUT = ROOT / "evidence/leader_mentions_v1"
UA = "PortfolioOptimizerResearch/2.0 contact=local-research"
# SEC Archives require a contact email (fair-access policy); it is read from the environment and
# never written into the repository. efts and data.sec.gov accept the anonymous agent above.
ARCHIVE_UA = os.environ.get("SEC_USER_AGENT", UA)
TOP_LIQUID, N_LEADERS, N_CONTROLS = 200, 20, 50
HORIZONS = {"T1_new_mentioners_126d": 126, "T2_new_mentioners_252d": 252}
BAR = 0.025
SUFFIXES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HOLDINGS",
            "HOLDING", "GROUP", "LLC", "LP", "NV", "SA", "AG", "THE", "NEW", "CL", "SE", "LLP", "TRUST", "INTL"}
SURNAME_FIRST = {"SCHWAB CHARLES": "CHARLES SCHWAB", "LILLY ELI": "ELI LILLY"}   # SEC conformed order
LEGAL_INITIALS = {"L.P.", "N.V.", "S.A.", "P.L.C.", "L.L.C.", "S.E.", "A.G.", "L.L.P.", "S.P.A.", "B.V."}
DESCRIPTIVE = {"INTERNATIONAL", "ENTERPRISES", "TECHNOLOGIES", "TECHNOLOGY"}


def load_names() -> pd.DataFrame:
    frames = []
    for path in sorted((ROOT / "data/sec_fsds_history_v1").glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive, archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["cik", "name", "form", "filed"], low_memory=False)
        except Exception:                                    # noqa: BLE001
            continue
        frames.append(sub[sub.form.astype(str).str.upper().isin(["10-K", "10-Q"])])
    names = pd.concat(frames, ignore_index=True)
    names["cik10"] = names.cik.astype("int64").astype(str).str.zfill(10)
    names["available"] = pd.to_datetime(names.filed.astype(str), format="%Y%m%d") + pd.Timedelta(days=1)
    return names[["cik10", "name", "available"]].sort_values("available")


def clean_name(name: str, words: set[str] | None = None) -> str:
    """As-filed SEC name -> search phrase (registry + its 2026-10-15 amendment)."""
    s = re.sub(r"\s*/\s*[A-Z]{2,3}\b/?", " ", str(name).upper())          # state tags: /TX, /MA, /DE/
    tokens = re.sub(r"[^A-Z0-9 &\-]", " ", s).split()
    # Rebuild punctuation SEC conformed names drop (Step 363 amendment 2): "D R HORTON" -> "D.R. HORTON",
    # "AMAZON COM" -> "AMAZON.COM". Full-text search matches the punctuated form (151 hits vs 1 for Amazon).
    merged, i = [], 0
    while i < len(tokens):
        if len(tokens[i]) == 1 and tokens[i].isalpha():
            run = []
            while i < len(tokens) and len(tokens[i]) == 1 and tokens[i].isalpha():
                run.append(tokens[i]); i += 1
            merged.append(".".join(run) + "." if len(run) > 1 else run[0])
        else:
            merged.append(tokens[i]); i += 1
    tokens = [t for k, t in enumerate(merged) if k == 0 or not (len(t) == 1 and t.isalpha())] or merged
    if "COM" in tokens:
        k = tokens.index("COM")
        if k > 0:
            tokens = tokens[:k - 1] + [tokens[k - 1] + ".COM"] + tokens[k + 1:]
    core = [t for k, t in enumerate(tokens)
            if (k == 0 and t not in {"THE"}) or (t not in SUFFIXES and t not in LEGAL_INITIALS)]
    if len(core) > 1 and core[-1].endswith(".") and "." in core[-1][:-1]:
        core = [core[-1]] + core[:-1]                             # "HORTON D.R." -> "D.R. HORTON"
    while core and core[-1] == "&":
        core = core[:-1]
    short = [t for k, t in enumerate(core) if k == 0 or t not in DESCRIPTIVE] or core
    flipped = SURNAME_FIRST.get(" ".join(short))
    if flipped:
        return flipped
    if words is not None and len(short) == 1 and short[0].lower() in words and len(core) > 1:
        return " ".join(core)
    return " ".join(short) if short else " ".join(tokens[:1])


def quarters():
    return pd.period_range("2012Q1", "2025Q3", freq="Q")


def stage_leaders() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    names = load_names()
    words = {w.strip() for w in Path("/usr/share/dict/words").read_text().splitlines() if w.strip().islower()}
    dates, cols = prices.index, np.array(prices.columns)
    px, dv = prices.to_numpy(), dollar.to_numpy()
    rows = []
    for q in quarters():
        start = q.start_time
        t = dates.searchsorted(start) - 1                      # last trading day before Q starts
        liquid = (px[t] >= 5) & (dv[t] >= 5e6)
        pool = np.argsort(-np.where(liquid, dv[t], -np.inf))[:TOP_LIQUID]
        r12 = px[t, pool] / px[t - 252, pool] - 1.0
        order = pool[np.argsort(-np.nan_to_num(r12, nan=-np.inf))][:N_LEADERS]
        known = names[names.available <= start].groupby("cik10").name.last()
        for i in order:
            cik = cols[i]
            raw = known.get(cik)
            search = clean_name(raw, words) if isinstance(raw, str) else None
            excluded = (search is None or len(search) < 4
                        or (len(search.split()) == 1 and search.lower() in words))
            rows.append({"quarter": str(q), "cik10": cik, "as_filed_name": raw, "search_name": search,
                         "trailing_12m_return": float(px[t, i] / px[t - 252, i] - 1.0), "excluded": bool(excluded)})
    leaders = pd.DataFrame(rows)
    leaders.to_csv(OUTPUT / "leaders.csv", index=False)
    print(f"{len(leaders)} leader-quarters, {leaders.cik10.nunique()} distinct leaders, "
          f"{leaders.excluded.sum()} excluded as ambiguous or unnamed")
    print("excluded names:", sorted(set(leaders[leaders.excluded].search_name.dropna()))[:60])
    print(leaders[~leaders.excluded].search_name.value_counts().head(30).to_string())
    return 0


def fts(name: str, start: str, end: str) -> dict:
    """All hits for an exact phrase in 10-K/10-Q/8-K filed between start and end, cached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]+", "_", f"{name}_{start}_{end}")
    path = CACHE / f"{key}.json"
    if path.is_file():
        return json.loads(path.read_text())
    hits, total, offset = [], None, 0
    while total is None or (offset < total and offset < 10000):
        params = urllib.parse.urlencode({"q": f'"{name}"', "forms": "10-K,10-Q,8-K", "dateRange": "custom",
                                         "startdt": start, "enddt": end, "from": offset})
        url = f"https://efts.sec.gov/LATEST/search-index?{params}"
        data, last_error = None, None
        for attempt in range(7):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = json.loads(resp.read())
                if "hits" not in payload:                      # EDGAR sometimes returns an error body
                    raise ValueError(str(payload)[:200])
                data = payload
                break
            except Exception as exc:                           # noqa: BLE001
                last_error = str(exc)[:200]
                time.sleep(min(60, 2 ** attempt))
        if data is None:
            out = {"name": name, "start": start, "end": end, "total": None, "capped": False, "hits": hits,
                   "failed": True, "error": last_error, "failed_at_offset": offset}
            path.write_text(json.dumps(out))
            return out
        total = data["hits"]["total"]["value"]
        page = data["hits"]["hits"]
        hits += [{"id": h["_id"], "ciks": h["_source"].get("ciks", []), "file_date": h["_source"].get("file_date"),
                  "form": h["_source"].get("form"), "file_type": h["_source"].get("file_type")} for h in page]
        if not page:
            break
        offset += len(page)
        time.sleep(0.15)
    out = {"name": name, "start": start, "end": end, "total": total, "capped": bool(total and total >= 10000), "hits": hits,
           "failed": False}
    path.write_text(json.dumps(out))
    time.sleep(0.15)
    return out


def stage_acquire() -> int:
    leaders = pd.read_csv(OUTPUT / "leaders.csv", dtype={"cik10": str})
    leaders = leaders[~leaders.excluded]
    capped, n, failures = 0, 0, 0
    for row in leaders.itertuples():
        q = pd.Period(row.quarter, freq="Q")
        cur = fts(row.search_name, q.start_time.strftime("%Y-%m-%d"), q.end_time.strftime("%Y-%m-%d"))
        prev = fts(row.search_name, (q.start_time - pd.DateOffset(years=1)).strftime("%Y-%m-%d"),
                   (q.start_time - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        capped += cur["capped"] + prev["capped"]
        failed = cur.get("failed", False) or prev.get("failed", False)
        failures += int(failed)
        n += 1
        if n % 50 == 0:
            print(f"  {n}/{len(leaders)} leader-quarters, capped queries so far {capped}", flush=True)
    print(f"done: {n} leader-quarters, {capped} queries hit the 10,000 cap, "
          f"{failures} leader-quarters with a failed query (skipped in the screen)")
    return 0


def new_mentions() -> pd.DataFrame:
    leaders = pd.read_csv(OUTPUT / "leaders.csv", dtype={"cik10": str})
    leaders = leaders[~leaders.excluded]
    rows = []
    for row in leaders.itertuples():
        q = pd.Period(row.quarter, freq="Q")
        cur = fts(row.search_name, q.start_time.strftime("%Y-%m-%d"), q.end_time.strftime("%Y-%m-%d"))
        prev = fts(row.search_name, (q.start_time - pd.DateOffset(years=1)).strftime("%Y-%m-%d"),
                   (q.start_time - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        if cur.get("failed") or prev.get("failed"):
            continue                                             # cannot establish 'new' without both queries
        before = {c for h in prev["hits"] for c in h["ciks"]}
        seen = {}
        for h in cur["hits"]:
            for c in h["ciks"]:
                if c != row.cik10 and c not in before and c not in seen:
                    seen[c] = h
        for c, h in seen.items():
            rows.append({"quarter": row.quarter, "cik10": c, "leader_cik": row.cik10, "leader": row.search_name,
                         "doc_id": h["id"], "file_date": h["file_date"], "form": h["form"], "capped": cur["capped"]})
    return pd.DataFrame(rows)


def fetch_sentences(doc_id: str, cik: str, name: str) -> list[str]:
    adsh, filename = doc_id.split(":", 1)
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": ARCHIVE_UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.;:])\s+", text)
    pat = re.compile(re.escape(name), re.IGNORECASE)
    return [s[:400] for s in sentences if pat.search(s)][:4]


def stage_precision() -> int:
    nm = new_mentions()
    nm.to_csv(OUTPUT / "new_mentions_all.csv", index=False)
    design = nm[nm.quarter <= "2018Q4"]
    sample = design.sample(n=min(50, len(design)), random_state=20261015)
    rows = []
    for r in sample.itertuples():
        try:
            sents = fetch_sentences(r.doc_id, r.cik10, r.leader)
        except Exception as exc:                               # noqa: BLE001
            sents = [f"FETCH FAILED: {exc}"]
        rows.append({"quarter": r.quarter, "mentioner_cik": r.cik10, "leader": r.leader, "form": r.form,
                     "doc_id": r.doc_id, "sentences": " || ".join(sents), "classification": ""})
        time.sleep(0.15)
    pd.DataFrame(rows).to_csv(OUTPUT / "precision_sample.csv", index=False)
    print(f"new mentions: {len(nm)} (design {len(design)}); sample of {len(rows)} written for hand classification")
    return 0


def stage_screen() -> int:
    prec = pd.read_csv(OUTPUT / "precision_sample.csv")
    assert prec.classification.notna().all() and (prec.classification != "").all(), "classify the precision sample first"
    rng = np.random.default_rng(20261018)
    nm = pd.read_csv(OUTPUT / "new_mentions_all.csv", dtype={"cik10": str, "leader_cik": str})
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    pairs = net.load_pairs(net.EXPERIMENTS["etnic"])
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    px, dv = prices.to_numpy(), dollar.to_numpy()
    peer_cache, rows = {}, []
    for q, g in nm.groupby("quarter"):
        period = pd.Period(q, freq="Q")
        t = dates.searchsorted(period.end_time) - 1
        if t + 1 + max(HORIZONS.values()) >= len(dates):
            continue
        when = dates[t]
        year = a19.tnic_year_for(when)
        if year not in peer_cache:
            mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
            e = pairs[pairs.year == year]
            c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
            ok = c1.notna() & c2.notna()
            peer_cache[year] = pd.DataFrame({"a": c1[ok], "b": c2[ok]}).groupby("a").b.apply(set).to_dict()
        peers = peer_cache[year]
        groups = a19.sic_as_of(sic, when).reindex(cols)
        sic2, sic3 = groups.str[:2].to_numpy(dtype=object), groups.str[:3].to_numpy(dtype=object)
        liquid = (px[t] >= 5) & (dv[t] >= 5e6) & pd.notna(groups).to_numpy()
        mentioners = set(g.cik10)
        events = []
        for c, gg in g.groupby("cik10"):
            if c not in col_pos or not liquid[col_pos[c]]:
                continue
            j = col_pos[c]
            leaders = set(gg.leader_cik)
            lead_sic3 = {sic3[col_pos[l]] for l in leaders if l in col_pos}
            lead_peers = set().union(*[peers.get(l, set()) for l in leaders])
            if sic3[j] in lead_sic3 or c in lead_peers:
                continue
            events.append((c, j, leaders, lead_peers))
        for c, j, leaders, lead_peers in events:
            pool = [k for k in np.flatnonzero(liquid & (sic2 == sic2[j]))
                    if cols[k] not in mentioners and cols[k] not in lead_peers and cols[k] not in leaders and k != j]
            if len(pool) < 5:
                continue
            ctrl = rng.choice(pool, size=N_CONTROLS, replace=True)
            row = {"quarter": q, "cik10": c, "leaders": "|".join(sorted(leaders)),
                   "own_12m_return": float(px[t, j] / px[t - 252, j] - 1.0)}
            for name, h in HORIZONS.items():
                f = px[t + 1 + h, j] / px[t + 1, j] - 1.0
                cc = np.nanmean(px[t + 1 + h, ctrl] / px[t + 1, ctrl] - 1.0)
                row[name] = f - cc if np.isfinite(f) and np.isfinite(cc) else np.nan
            rows.append(row)
    ev = pd.DataFrame(rows)
    ev.to_csv(OUTPUT / "events.csv", index=False)

    def stats(frame, col):
        frame = frame.dropna(subset=[col])
        qm = frame.groupby("quarter")[col].mean()
        obs = qm.mean()
        keys = list(qm.index)
        draws = []
        for _ in range(4000):
            starts = rng.integers(0, max(1, len(keys) - 2), size=int(np.ceil(len(keys) / 2)))
            pick = [keys[s + o] for s in starts for o in range(2) if s + o < len(keys)][:len(keys)]
            draws.append(qm[pick].mean() - obs)
        top = frame[col].sort_values(ascending=False).index[:10]
        q_wo = frame.drop(top).groupby("quarter")[col].mean().mean()
        return {"firm_events": int(len(frame)), "quarters": int(len(qm)), "mean_of_quarter_means": float(obs),
                "firm_median": float(frame[col].median()), "share_positive": float((frame[col] > 0).mean()),
                "bootstrap_p": float((np.abs(np.array(draws)) >= abs(obs)).mean()), "without_top10": float(q_wo)}

    results = {}
    rel = prec.classification.str.lower().str.startswith("rel").mean()
    print(f"precision sample: relationship share {rel:.0%} of {len(prec)}")
    for name in HORIZONS:
        d = stats(ev[ev.quarter <= "2018Q4"], name)
        h = stats(ev[ev.quarter >= "2019Q1"], name)
        crit = {"design_mean_positive_p_below_bar": d["mean_of_quarter_means"] > 0 and d["bootstrap_p"] < BAR,
                "holdout_mean_positive": h["mean_of_quarter_means"] > 0,
                "design_survives_dropping_top10": d["without_top10"] > 0,
                "design_mean_above_50bps": d["mean_of_quarter_means"] > 0.005}
        results[name] = {"design": d, "holdout": h, "criteria": crit, "passes": all(crit.values())}
        print(f"\n== {name}")
        for lab, s in (("design", d), ("holdout", h)):
            print(f"  {lab:8s} firm-events {s['firm_events']:5d} quarters {s['quarters']:3d} mean {s['mean_of_quarter_means']:+.2%} "
                  f"firm median {s['firm_median']:+.2%} positive {s['share_positive']:.0%} p {s['bootstrap_p']:.4f} "
                  f"without top-10 {s['without_top10']:+.2%}")
        for k, v in crit.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print(f"  {name} {'PASSES' if results[name]['passes'] else 'FAILS'}")
    print(f"\ndiagnostic: mentioners' own trailing 12m return, median {ev.own_12m_return.median():+.1%}")
    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "precision_relationship_share": float(rel),
        "labelled_as": "business relationships" if rel >= 0.25 else "mentions (precision below 25%)",
        "results": results, "live_trading_enabled": False, "strategy_promotion_authorized": False},
        indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    json.loads(REGISTRY.read_text())
    stage = sys.argv[1]
    raise SystemExit({"leaders": stage_leaders, "acquire": stage_acquire, "precision": stage_precision,
                      "screen": stage_screen}[stage]())
