#!/usr/bin/env python3
"""A25 v2: keep only mentions whose sentence describes a real business relationship.

Pre-registered in config/leader_mentions_registry_v2.json (committed before any v2 sentence was
fetched). Stages, in order:

    SEC_USER_AGENT='... email' python scripts/run_leader_mentions_v2.py fetch       # sentences, cached, resumable
    python scripts/run_leader_mentions_v2.py filter                                 # apply the declared rule
    python scripts/run_leader_mentions_v2.py precision                              # fresh 50 to hand-read
    python scripts/run_leader_mentions_v2.py screen                                 # only if precision >= 50%
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_leader_mentions_v1 as v1  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/leader_mentions_registry_v2.json"
OUTPUT = ROOT / "evidence/leader_mentions_v2"
CACHE = ROOT / "data/edgar_fts_leader_mentions_v1/sentences_v2.jsonl"
FIN_SIC2 = {"60", "61", "62", "67"}


def candidates() -> pd.DataFrame:
    nm = pd.read_csv(ROOT / "evidence/leader_mentions_v1/new_mentions_all.csv", dtype={"cik10": str, "leader_cik": str})
    last = a19.load_sic().groupby("cik10").sic4.last()
    nm["leader_sic2"] = nm.leader_cik.map(last).str[:2]
    return nm[~nm.leader_sic2.isin(FIN_SIC2)].reset_index(drop=True)


def stage_fetch() -> int:
    reg = json.loads(REGISTRY.read_text())
    assert reg["registered_before_any_v2_sentence_was_fetched"]
    nm = candidates()
    done = set()
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            r = json.loads(line)
            done.add((r["doc_id"], r["leader"]))
    todo = [r for r in nm.itertuples() if (r.doc_id, r.leader) not in done]
    print(f"{len(nm)} candidate mentions; {len(done)} cached; fetching {len(todo)}", flush=True)
    lock, write_lock, last = threading.Lock(), threading.Lock(), [0.0]

    def throttle():
        with lock:
            wait = last[0] + 0.14 - time.monotonic()          # about 7 requests a second, under SEC's 10
            if wait > 0:
                time.sleep(wait)
            last[0] = time.monotonic()

    def work(r):
        throttle()
        try:
            sents, err = v1.fetch_sentences(r.doc_id, r.cik10, r.leader), None
        except Exception as exc:                               # noqa: BLE001
            sents, err = [], str(exc)[:120]
        rec = {"doc_id": r.doc_id, "leader": r.leader, "sentences": sents, "error": err}
        with write_lock, CACHE.open("a") as handle:
            handle.write(json.dumps(rec) + "\n")
        return err is None

    ok = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, fut in enumerate(as_completed([pool.submit(work, r) for r in todo]), 1):
            ok += fut.result()
            if n % 250 == 0:
                print(f"  {n}/{len(todo)} fetched, {ok} ok", flush=True)
    print(f"done: {ok}/{len(todo)} fetched without error")
    return 0


def keep(sentences: list[str], rel: list[str], excl: list[str]) -> bool:
    for s in sentences:
        low = s.lower()
        if any(t in low for t in rel) and not any(t in low for t in excl):
            return True
    return False


def stage_filter() -> int:
    reg = json.loads(REGISTRY.read_text())["construction"]
    rel, excl = [t.lower() for t in reg["relationship_terms"]], [t.lower() for t in reg["exclusion_terms"]]
    cache = {}
    for line in CACHE.read_text().splitlines():
        r = json.loads(line)
        cache[(r["doc_id"], r["leader"])] = r
    nm = candidates()
    flags, sentences, unfetched = [], [], 0
    for r in nm.itertuples():
        c = cache.get((r.doc_id, r.leader))
        if c is None or c["error"]:
            unfetched += 1
            flags.append(False); sentences.append("")
            continue
        flags.append(keep(c["sentences"], rel, excl)); sentences.append(" || ".join(c["sentences"]))
    nm["kept"], nm["sentences"] = flags, sentences
    OUTPUT.mkdir(parents=True, exist_ok=True)
    nm.to_csv(OUTPUT / "candidates_with_sentences.csv", index=False)
    kept = nm[nm.kept].drop(columns=["sentences"])
    kept.to_csv(OUTPUT / "new_mentions_all.csv", index=False)
    print(f"candidates {len(nm)}; unfetchable {unfetched}; kept {len(kept)} "
          f"(design {int((kept.quarter <= '2018Q4').sum())}, holdout {int((kept.quarter >= '2019Q1').sum())})")
    print(kept.leader.value_counts().head(20).to_string())
    return 0


def stage_precision() -> int:
    nm = pd.read_csv(OUTPUT / "candidates_with_sentences.csv", dtype={"cik10": str})
    design = nm[nm.kept & (nm.quarter <= "2018Q4")]
    sample = design.sample(n=min(50, len(design)), random_state=20261016)
    out = sample[["quarter", "cik10", "leader", "form", "doc_id", "sentences"]].rename(columns={"cik10": "mentioner_cik"})
    out["classification"] = ""
    out.to_csv(OUTPUT / "precision_sample.csv", index=False)
    print(f"fresh precision sample of {len(out)} written")
    return 0


def stage_screen() -> int:
    prec = pd.read_csv(OUTPUT / "precision_sample.csv")
    share = prec.classification.str.lower().str.startswith("rel").mean()
    print(f"v2 precision: relationship share {share:.0%} of {len(prec)}")
    if share < 0.50:
        (OUTPUT / "result.json").write_text(json.dumps({
            "registry": str(REGISTRY.relative_to(ROOT)), "precision_relationship_share": float(share),
            "verdict": "closed at the precision gate: real relationships cannot be isolated from free filings text at scale; no return computed",
            "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2) + "\n")
        print("precision gate FAILS: no return computed, as registered")
        return 0
    v1.OUTPUT, v1.REGISTRY = OUTPUT, REGISTRY                    # reuse v1's screen verbatim on v2's mentions
    return v1.stage_screen()


if __name__ == "__main__":
    raise SystemExit({"fetch": stage_fetch, "filter": stage_filter, "precision": stage_precision,
                      "screen": stage_screen}[sys.argv[1]]())
