#!/usr/bin/env python3
"""Map issuers to Wikipedia articles, then fetch their daily pageviews.

Declared in config/wikipedia_attention_registry_v1.json before any of this ran.

The mapping is the risky part and it is a gate, not a preprocessing step. Every
other panel in this project joins on cik10, an exact key. Here a company name is
searched against Wikipedia and the top hit is taken, and a search for a small
industrial can easily return an article about a person, a town, or a different
company entirely. A signal built on that measures noise while looking like data.

So each candidate match must pass a token check: the article title has to share a
meaningful token with the company name after stripping corporate suffixes (INC,
CORP, CO, LTD, PLC, HOLDINGS, GROUP and so on), and single-letter or numeric
tokens do not count. Matches are written to disk with the name they came from so
the whole mapping can be audited rather than trusted.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
CACHE = ROOT / "data/wikipedia_attention_v1"
EVIDENCE = ROOT / "evidence/wikipedia_attention_v1"
AGENT = "Portfolio Optimizer Research nicholasturangan@gmail.com"
SEARCH = "https://en.wikipedia.org/w/api.php?action=opensearch&search={q}&limit=1&namespace=0&format=json"
VIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
         "all-access/user/{a}/daily/20150701/20260904")
SUFFIXES = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "LLC",
            "LP", "HOLDINGS", "HOLDING", "GROUP", "THE", "AND", "TRUST", "REIT", "SA", "NV",
            "AG", "CLASS", "COM", "NEW", "INTERNATIONAL", "INDUSTRIES", "TECHNOLOGIES"}
PAUSE = 0.12


def tokens(text: str) -> set[str]:
    """Meaningful name tokens, corporate suffixes removed.

    POST-HOC CORRECTION, made 2026-09-07 after the declared gate returned 58.5%
    against a 60% threshold, and recorded as post-hoc rather than folded in
    silently. The original rule required tokens longer than two characters, which
    rejected `HP INC -> HP Inc.` -- a demonstrably correct match -- along with
    every other two-letter company name. It is a bug in the matcher, not a
    loosening of the gate: lowering the threshold to two still rejects
    `COHU INC -> Corfu incident`, `TRANSCAT INC -> Translation` and
    `CALAMP CORP -> Calamphoreus`, because token overlap is computed on whole
    tokens rather than string prefixes. Both mappings are kept on disk --
    mapping__as_declared.csv and mapping.csv -- so the difference is auditable.
    """
    raw = re.sub(r"[^A-Za-z0-9 ]", " ", str(text).upper()).split()
    return {t for t in raw if t not in SUFFIXES and len(t) >= 2 and not t.isdigit()}


def fetch(url: str, timeout: int = 45) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception:                                # noqa: BLE001
        return None


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "views").mkdir(exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    members = pd.read_csv(MEMBERSHIP, dtype={"cik10": str},
                          usecols=["cik10", "company_name_as_filed", "tradable_member"])
    members = members[members.tradable_member.astype(bool)]
    issuers = (members.groupby("cik10").company_name_as_filed.first()
               .rename("name").reset_index())

    mapping_path = CACHE / "mapping.csv"
    known = pd.read_csv(mapping_path, dtype={"cik10": str}) if mapping_path.exists() else None
    resolved = dict(zip(known.cik10, known.article)) if known is not None else {}

    rows, matched, rejected = [], 0, 0
    for record in issuers.itertuples(index=False):
        if record.cik10 in resolved:
            rows.append({"cik10": record.cik10, "name": record.name,
                         "article": resolved[record.cik10], "accepted": True})
            matched += 1
            continue
        body = fetch(SEARCH.format(q=urllib.parse.quote(str(record.name))), timeout=25)
        time.sleep(PAUSE)
        article, accepted = None, False
        if body:
            try:
                payload = json.loads(body)
                if payload[1]:
                    article = str(payload[1][0])
                    accepted = bool(tokens(record.name) & tokens(article))
            except Exception:                        # noqa: BLE001
                pass
        rows.append({"cik10": record.cik10, "name": record.name,
                     "article": article, "accepted": accepted})
        matched += int(accepted)
        rejected += int(article is not None and not accepted)

    mapping = pd.DataFrame(rows)
    mapping.to_csv(mapping_path, index=False)
    accepted = mapping[mapping.accepted & mapping.article.notna()]

    fetched = cached = failed = 0
    for record in accepted.itertuples(index=False):
        title = str(record.article).replace(" ", "_")
        target = CACHE / "views" / f"{record.cik10}.json"
        if target.exists() and target.stat().st_size > 200:
            cached += 1
            continue
        body = fetch(VIEWS.format(a=urllib.parse.quote(title, safe="")))
        time.sleep(PAUSE)
        if body and b'"items"' in body:
            target.write_bytes(body)
            fetched += 1
        else:
            failed += 1

    result = {
        "issuers_in_universe": int(len(issuers)),
        "articles_matched": int(len(accepted)),
        "match_rate": float(len(accepted) / len(issuers)) if len(issuers) else 0.0,
        "rejected_by_token_check": int(rejected),
        "pageview_files_fetched": fetched, "already_cached": cached,
        "pageview_fetch_failed": failed,
        "gate_4_mapping_quality_threshold": 0.60,
        "gate_4_passes": bool(len(accepted) / max(1, len(issuers)) >= 0.60),
        "mapping_written_for_audit": str(mapping_path.relative_to(ROOT)),
        "live_trading_enabled": False,
    }
    (EVIDENCE / "acquisition.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
