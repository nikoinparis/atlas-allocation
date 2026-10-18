#!/usr/bin/env python3
"""Forward AVOID list: liquid firms that newly disclose a real relationship with a current market
leader (protocol avoid_hot_leader_ties_v1). Quarterly; idempotent; safe to call every Friday.

Reuses A25's search, name cleaning and v2 relationship filter verbatim (Steps 363-367). Each
quarter's list and controls are frozen to a CSV whose hash is pinned in the decision record, and
each quarter is scored once, 52 weeks later, against its controls.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.systematic_trader.forward_evidence import ForwardEvidenceError, append_record, file_hash, read_and_verify_log  # noqa: E402

LOCAL_UA = ROOT / "config/local/sec_user_agent.txt"
if not os.environ.get("SEC_USER_AGENT") and LOCAL_UA.exists():
    os.environ["SEC_USER_AGENT"] = LOCAL_UA.read_text().strip()

import acquire_sec_earnings_8k_v1 as e8k  # noqa: E402
import run_leader_mentions_v1 as v1  # noqa: E402
import run_leader_mentions_v2 as v2  # noqa: E402
import run_network_peer_screen_v1 as net  # noqa: E402
import run_steady_riser_v1 as sr  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

PROTOCOL = ROOT / "config/forward/avoid_hot_leader_ties_v1.json"
OUTPUT = ROOT / "evidence/forward_avoid_hot_leader_ties_v1"
FIRST = "2026-07-01"
N_CONTROLS, TOP_LIQUID, N_LEADERS = 50, 200, 20


def due_quarter(today: pd.Timestamp) -> pd.Period | None:
    q = (today - pd.Timedelta(days=14)).to_period("Q")
    while q.end_time.normalize() + pd.Timedelta(days=14) > today:
        q -= 1
    if q.start_time < pd.Timestamp(FIRST) or today > q.end_time.normalize() + pd.Timedelta(days=60):
        return None
    return q


def leader_name(cik: str, names: pd.DataFrame, when: pd.Timestamp, words: set[str]) -> str | None:
    known = names[(names.cik10 == cik) & (names.available <= when)]
    raw = known.name.iloc[-1] if len(known) else None
    if raw is None:                                           # filers after FSDS's 2022Q4 end
        config = json.loads(e8k.CONFIG.read_text())
        fetcher = e8k.Fetcher(e8k.DEFAULT_CACHE, v1.UA, config["minimum_seconds_between_requests"],
                              config["request_timeout_seconds"], config["maximum_attempts"])
        raw = fetcher.json(config["source_endpoint"].format(cik10=cik), f"submissions_{cik}")[0].get("name")
    if not raw:
        return None
    search = v1.clean_name(raw, words)
    if len(search) < 4 or (len(search.split()) == 1 and search.lower() in words):
        return None
    return search


def decide(q: pd.Period, now: datetime) -> dict:
    if not os.environ.get("SEC_USER_AGENT"):
        raise ForwardEvidenceError("SEC Archives need a contact agent: set SEC_USER_AGENT or config/local/sec_user_agent.txt")
    v1.ARCHIVE_UA = os.environ["SEC_USER_AGENT"]
    prices, dollar = sr.load()
    sic = a19.load_sic()
    names = v1.load_names()
    words = {w.strip() for w in Path("/usr/share/dict/words").read_text().splitlines() if w.strip().islower()}
    reg = json.loads(v2.REGISTRY.read_text())["construction"]
    rel, excl = [t.lower() for t in reg["relationship_terms"]], [t.lower() for t in reg["exclusion_terms"]]

    start = q.start_time
    w0 = prices.index[prices.index <= start][-1]
    pos = prices.index.get_loc(w0)
    dv0 = dollar[dollar.index <= start].iloc[-1].reindex(prices.columns)
    liquid0 = (prices.iloc[pos] >= 5) & (dv0 >= 5e6)
    pool = dv0[liquid0].sort_values(ascending=False).index[:TOP_LIQUID]
    r52 = (prices.iloc[pos][pool] / prices.iloc[pos - 52][pool] - 1).dropna().sort_values(ascending=False)
    sic_q = a19.sic_as_of(sic, start)
    leaders = []
    for cik in r52.index:
        if str(sic_q.get(cik, ""))[:2] in v2.FIN_SIC2:
            continue
        name = leader_name(cik, names, start, words)
        if name:
            leaders.append((cik, name))
        if len(leaders) == N_LEADERS:
            break

    s0, e0 = start.strftime("%Y-%m-%d"), q.end_time.strftime("%Y-%m-%d")
    p0, p1 = (start - pd.DateOffset(years=1)).strftime("%Y-%m-%d"), (start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    mentions = {}
    for cik, name in leaders:
        cur, prev = v1.fts(name, s0, e0), v1.fts(name, p0, p1)
        if cur.get("failed") or prev.get("failed"):
            continue
        before = {c for h in prev["hits"] for c in h["ciks"]}
        for h in cur["hits"]:
            for c in h["ciks"]:
                if c != cik and c not in before:
                    mentions.setdefault((c, cik, name), h["id"])

    entry_week = prices.index[-1]
    groups = a19.sic_as_of(sic, entry_week).reindex(prices.columns)
    sic2, sic3 = groups.str[:2], groups.str[:3]
    dv_now = dollar.iloc[-1].reindex(prices.columns)
    liquid = (prices.iloc[-1] >= 5) & (dv_now >= 5e6) & groups.notna()
    pairs = net.load_pairs(net.EXPERIMENTS["etnic"])
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"], links["last_date"] = pd.to_datetime(links.first_date), pd.to_datetime(links.last_date)
    mapping = a19.gvkey_to_cik(links, start)
    e = pairs[pairs.year == pairs.year.max()]
    c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
    peers = pd.DataFrame({"a": c1, "b": c2}).dropna().groupby("a").b.apply(set).to_dict()

    kept = {}
    for (c, lcik, name), doc in mentions.items():
        if c not in prices.columns or not bool(liquid.get(c, False)):
            continue
        if sic3.get(c) == sic3.get(lcik) or c in peers.get(lcik, set()):
            continue
        try:
            sentences = v1.fetch_sentences(doc, c, name)
        except Exception:                                      # noqa: BLE001
            continue
        if v2.keep(sentences, rel, excl):
            kept.setdefault(c, {"leaders": set(), "sentences": []})
            kept[c]["leaders"].add(name)
            kept[c]["sentences"] += sentences[:2]

    rng = np.random.default_rng(int(q.start_time.strftime("%Y%m%d")))
    rows = []
    listed = set(kept)
    for c, info in sorted(kept.items()):
        lead_peers = set().union(*[peers.get(l, set()) for l, n in leaders if n in info["leaders"]])
        pool_c = [k for k in prices.columns[(liquid & (sic2 == sic2[c])).to_numpy()]
                  if k not in listed and k not in lead_peers and k != c]
        if len(pool_c) < 5:
            continue
        ctrl = list(rng.choice(pool_c, size=N_CONTROLS, replace=True))
        rows.append({"cik10": c, "leaders": "|".join(sorted(info["leaders"])), "entry_price": float(prices.iloc[-1][c]),
                     "controls": "|".join(ctrl), "evidence": " || ".join(info["sentences"])[:600]})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"avoid_{q}.csv"
    if path.exists():
        raise ForwardEvidenceError(f"{path.name} already exists; a frozen list is never rewritten")
    pd.DataFrame(rows, columns=["cik10", "leaders", "entry_price", "controls", "evidence"]).to_csv(path, index=False)
    return {"quarter": str(q), "decision_date": now.date().isoformat(), "entry_week": str(entry_week.date()),
            "leaders": [n for _, n in leaders], "new_mentions": len(mentions), "avoid_firms": len(rows),
            "list_file": str(path.relative_to(ROOT)), "list_sha256": file_hash(path)}


def score(record: dict, prices: pd.DataFrame) -> dict | None:
    entry = pd.Timestamp(record["entry_week"])
    if entry not in prices.index:
        return None
    pos = prices.index.get_loc(entry)
    if pos + 52 >= len(prices.index):
        return None
    path = ROOT / record["list_file"]
    if file_hash(path) != record["list_sha256"]:
        raise ForwardEvidenceError(f"{path.name} does not match its pinned hash")
    lst = pd.read_csv(path, dtype={"cik10": str})
    p0, p1 = prices.iloc[pos], prices.iloc[pos + 52]
    diffs = []
    for r in lst.itertuples():
        ctrl = r.controls.split("|")
        f = p1.get(r.cik10) / p0.get(r.cik10) - 1
        c = np.nanmean((p1.reindex(ctrl) / p0.reindex(ctrl) - 1).to_numpy())
        if np.isfinite(f) and np.isfinite(c):
            diffs.append(f - c)
    return {"quarter": record["quarter"], "realization_date": str(prices.index[pos + 52].date()),
            "scored_firms": len(diffs), "avoid_minus_control_52w": float(np.mean(diffs)) if diffs else None}


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    now = datetime.now(timezone.utc)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dpath, opath = OUTPUT / "decisions.jsonl", OUTPUT / "observations.jsonl"
    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=FIRST)
    added = {"decisions": 0, "observations": 0}
    q = due_quarter(pd.Timestamp(now.date()))
    if q is not None and not any(r["quarter"] == str(q) for r in decisions):
        payload = {"record_type": "avoid_hot_leader_ties_decision_v1", "protocol_version": protocol["protocol_version"],
                   **decide(q, now), "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                   "execution_enabled": False}
        append_record(dpath, payload, date_field="decision_date", first_eligible_date=FIRST)
        added["decisions"] += 1
    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=FIRST)
    observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=FIRST)
    done = {o["quarter"] for o in observed}
    prices, _ = sr.load()
    for r in decisions:
        if r["quarter"] in done:
            continue
        s = score(r, prices)
        if s:
            append_record(opath, {"record_type": "avoid_hot_leader_ties_observation_v1", **s,
                                  "decision_record_hash": r["record_hash"], "recorded_at_utc": now.isoformat(),
                                  "forward_protocol_sha256": file_hash(PROTOCOL), "execution_enabled": False},
                          date_field="realization_date", first_eligible_date=FIRST)
            added["observations"] += 1
    observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=FIRST)
    status = {"protocol_version": protocol["protocol_version"], "role": "forward avoid list, not a strategy",
              "recorded_quarters": [r["quarter"] for r in decisions], "scored_quarters": len(observed),
              "latest_list_size": decisions[-1]["avoid_firms"] if decisions else None,
              "avoid_minus_control_52w": [o["avoid_minus_control_52w"] for o in observed],
              "generated_at_utc": now.isoformat(), "promotion_authorized": False, "execution_enabled": False,
              "live_trading_enabled": False}
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"added": added, **status}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
