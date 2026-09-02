#!/usr/bin/env python3
"""Extract customer-supplier edges from SEC filing text.

Specification comes from a direct read of Cohen & Frazzini, "Economic Links and
Predictable Returns", Journal of Finance 63(4), 1981-2011 (2008), pages 1983-1988,
read 2026-09-02 rather than recalled:

  - SFAS 131 requires disclosing the identity of any customer representing more than
    10% of total reported sales. So the threshold here is 10%, not the 5% used in the
    throwaway scope probe.
  - Their Table I: mean 19.80% / median 14.68% of sales to customer; mean 1.60
    customers per firm (median 1, max 20); link duration mean 2.7 years; customers sit
    above the 90th size percentile.
  - They used Compustat segment files, which are professionally curated from these same
    disclosures. This extractor reads the raw text instead, so recall is the thing to
    watch: their sample carried ~918 supplier firms per year.

The scope probe's naive pass ran at ~69% false positives, dominated by the bare token
"Company" and by regulator boilerplate (FDIC, SIPC). Three rules fix most of it:
directional grammar rather than proximity, an explicit self-reference filter, and a
requirement that the entity survive normalisation as a real multi-token name.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHES = ["data/sec_broad_identity_cache_v2", "data/sec_historical_identity_cache"]
THRESHOLD_PCT = 10.0          # SFAS 131 disclosure cutoff
WINDOW_BACK, WINDOW_FWD = 200, 300

SUFFIX = (r"Inc|Corp|Corporation|Company|Co|LLC|L\.L\.C|Ltd|Limited|LP|L\.P|plc|PLC|"
          r"N\.V|S\.A|AG|SE|AB|Group|Holdings|Technologies|Technology|Systems|Solutions|"
          r"Industries|Enterprises|Stores|Motors|Airlines|Pharmaceuticals|Networks|Labs|"
          r"Laboratories|Communications|Electronics|Semiconductor|Bank|Energy|Partners")

# An entity is 1-5 capitalised tokens ending in a corporate suffix, or a known bare-name
# megacap that files without one.
ENTITY = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&'.\-]{1,24}\s+){0,4}(?:" + SUFFIX + r")\.?)(?![A-Za-z])")
BARE = re.compile(r"\b(Apple|Walmart|Wal-Mart|Amazon|Boeing|Costco|Target|Verizon|"
                  r"Microsoft|Intel|Nvidia|Samsung|Toyota|Ford|Nokia|Ericsson|Huawei|"
                  r"Dell|Lenovo|Sony|Siemens|Airbus|Caterpillar|Deere|Tesla)\b")

# Directional grammar: the entity must be tied to the filer as a counterparty.
PATTERNS = [
    re.compile(r"sales\s+to\s+(?P<e>.{0,80}?)\s*(?:of|were|totaled|represent|account|"
               r"comprised|equal|accounted)", re.I | re.S),
    re.compile(r"(?:revenues?|sales|purchases)\s+from\s+(?P<e>.{0,80}?)\s*"
               r"(?:were|of|totaled|represent|account|comprised|accounted)", re.I | re.S),
    re.compile(r"(?P<e>.{0,80}?)\s+accounted\s+for\s+(?:approximately\s+)?[\d.]{1,5}\s*%",
               re.I | re.S),
    re.compile(r"(?:largest|major|principal|significant|primary|key)\s+"
               r"(?:customer|client)s?,?\s+(?P<e>.{0,80}?)[,.\(]", re.I | re.S),
    re.compile(r"(?:customer|client)s?,?\s+(?P<e>.{0,80}?),?\s+(?:which|who)\s+"
               r"(?:accounted|represented)", re.I | re.S),
]

TRIGGER = re.compile(r"sales to |revenues? from |purchases from |accounted for|"
                     r"largest customer|major customer|principal customer|"
                     r"significant customer|primary customer|key customer", re.I)
PCT = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)")

# Entities that are never commercial customers in this context.
NOT_A_CUSTOMER = re.compile(
    r"federal deposit|depositor[y|ies] insurance|securities investor protection|"
    r"internal revenue|financial accounting|public company accounting|"
    r"^(?:the\s+)?compan(?:y|ies)$|^group$|^systems?$|^corp(?:oration)?$|^inc$|"
    r"^holdings$|^technolog(?:y|ies)$|^solutions$|^partners$|^bank$|^limited$|^ltd$|"
    r"credit risk|cash equivalent|off-balance|united states|european union|"
    r"^(?:our|its|their|this|these|such|other|certain|various|two|three|one)\b|"
    r"generally accepted|new york stock|nasdaq stock|standard & poor", re.I)

STOPWORD_START = re.compile(r"^(The|Our|Its|Their|A|An|This|That|These|Those|Such|"
                            r"Certain|Various|Other|Two|Three|One|No|Approximately|"
                            r"Additionally|However|Further|Also|In|On|At|For|With|And)\s+",
                            re.I)


def clean_entity(raw: str) -> str | None:
    """Normalise a candidate name, or return None if it is not a usable entity."""
    s = re.sub(r"\s+", " ", raw).strip(" .,;:()[]\"'")
    prev = None
    while prev != s:                      # strip leading filler repeatedly
        prev = s
        s = STOPWORD_START.sub("", s).strip(" .,;:()[]\"'")
    if not s or len(s) < 4:
        return None
    if NOT_A_CUSTOMER.search(s):
        return None
    if not re.match(r"^[A-Z]", s):
        return None
    tokens = s.split()
    if len(tokens) > 7:
        return None
    # Reject strings that are only corporate suffixes with no distinguishing name.
    core = [t for t in tokens if not re.fullmatch(r"(?:" + SUFFIX + r")\.?", t)]
    if not core and not BARE.search(s):
        return None
    return s


def self_reference(entity: str, filer_names: set[str]) -> bool:
    """Filings say 'the Company' constantly; they also name themselves. Both are noise."""
    e = re.sub(r"[^a-z ]", "", entity.lower())
    for fn in filer_names:
        f = re.sub(r"[^a-z ]", "", fn.lower())
        if not f:
            continue
        if e.startswith(f[:12]) or f.startswith(e[:12]):
            return True
    return False


def filer_name_guess(text: str) -> set[str]:
    """Cheap self-name guesses from the filing's own cover page."""
    names = set()
    head = text[:6000]
    for m in re.finditer(r"\b((?:[A-Z][A-Za-z0-9&'.\-]{1,24}\s+){1,4}(?:" + SUFFIX + r")\.?)",
                         head):
        n = m.group(1).strip()
        if len(n) > 5 and not NOT_A_CUSTOMER.search(n):
            names.add(n)
    return set(list(names)[:6])


def extract_from_text(text: str, cik: str) -> list[dict]:
    """Return one edge per (customer, pct) found under directional customer grammar."""
    filer_names = filer_name_guess(text)
    out, seen = [], set()
    for t in TRIGGER.finditer(text):
        window = text[max(0, t.start() - WINDOW_BACK): t.end() + WINDOW_FWD]
        pcts = [float(p) for p in PCT.findall(window)]
        pcts = [p for p in pcts if THRESHOLD_PCT <= p <= 100]
        if not pcts:
            continue
        pct = max(pcts) if len(pcts) == 1 else min(pcts)
        for pat in PATTERNS:
            for m in pat.finditer(window):
                cand = m.group("e")
                ents = [x.group(1) for x in ENTITY.finditer(cand)]
                if not ents:
                    b = BARE.search(cand)
                    ents = [b.group(1)] if b else []
                for raw in ents:
                    ent = clean_entity(raw)
                    if not ent or self_reference(ent, filer_names):
                        continue
                    key = (ent.lower(), round(pct, 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"filer_cik": cik, "customer": ent, "pct": pct,
                                "context": re.sub(r"\s+", " ", window)[:400]})
    return out


def load_filings() -> list[tuple[str, str, str]]:
    files = []
    for c in CACHES:
        files += sorted((ROOT / c).glob("*.htm.gz"))
    out = []
    for f in files:
        m = re.match(r"filing_(\d{10})_", f.name)
        raw = gzip.open(f, "rb").read().decode("utf8", "ignore")
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))
        out.append((m.group(1) if m else "?", f.name, text))
    return out


def main() -> int:
    outdir = ROOT / "evidence" / "customer_edge_extraction_v1"
    outdir.mkdir(parents=True, exist_ok=True)
    filings = load_filings()
    edges, with_edge, concentration = [], set(), set()
    for cik, fname, text in filings:
        if TRIGGER.search(text) and PCT.search(text):
            concentration.add(fname)
        e = extract_from_text(text, cik)
        for x in e:
            x["filing"] = fname
        edges += e
        if e:
            with_edge.add(fname)
    n = len(filings)
    names = Counter(x["customer"] for x in edges)
    print(f"filings scanned                 : {n}")
    print(f"filings w/ concentration language: {len(concentration)}  ({len(concentration)/n:.1%})")
    print(f"filings yielding >=1 edge        : {len(with_edge)}  ({len(with_edge)/n:.1%})")
    print(f"edges                            : {len(edges)}")
    print(f"distinct named customers         : {len(names)}")
    if edges:
        pcts = sorted(x["pct"] for x in edges)
        print(f"pct of sales: median {pcts[len(pcts)//2]:.1f}%  mean {sum(pcts)/len(pcts):.1f}%"
              f"   (paper: median 14.68, mean 19.80)")
        per = Counter(x["filing"] for x in edges)
        vals = sorted(per.values())
        print(f"customers per filing: median {vals[len(vals)//2]}  mean {sum(vals)/len(vals):.2f}"
              f"   (paper: median 1, mean 1.60)")
    print("\ntop customers:")
    for s, c in names.most_common(20):
        print(f"   {c:>3}  {s}")
    json.dump(edges, open(outdir / "edges.json", "w"), indent=1)
    print(f"\nwrote {outdir/'edges.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
