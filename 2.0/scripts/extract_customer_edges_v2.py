#!/usr/bin/env python3
"""Extract customer-supplier edges from SEC filing text — v2.

Specification from a direct read of Cohen & Frazzini, "Economic Links and Predictable
Returns", Journal of Finance 63(4) (2008), pp. 1983-88: SFAS 131 requires naming any
customer above 10% of total sales; their Table I reports sales-to-customer mean 19.80%
median 14.68%, customers per firm mean 1.60 median 1.

v1 measured 73.3% precision on 60 hand-labelled edges, below the 85% gate. Its errors
fell into seven mechanical classes, and v2 targets six of them:

  own product/segment (5 errors)  - "revenues from OUR Unified Communications products"
  entity/pct misattribution (4)   - entity from one sentence, percentage from another
  wrong percentage type (3)       - a tax rate and a growth rate read as concentration
  page furniture (2)              - "42 Table of Contents Group companies"
  direction reversed (1)          - "Canadian Solar SUPPLIED 55% of our panels"
  anonymous defined term (1)      - the quoted label "Customer Group"

The structural fix is sentence-bounded extraction: an entity and a percentage must appear
in the SAME sentence to become an edge. Window-bounded matching caused every
misattribution error in v1.

Because v2's filters were designed against a labelled sample, precision must be
re-measured on a DIFFERENT random sample. Re-scoring on the same 60 would be fitting the
extractor to its own test.
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
THRESHOLD_PCT = 10.0
WINDOW_BACK, WINDOW_FWD = 200, 300

SUFFIX = (r"Inc|Corp|Corporation|Company|Co|LLC|L\.L\.C|Ltd|Limited|LP|L\.P|plc|PLC|"
          r"N\.V|S\.A|AG|SE|AB|Group|Holdings|Technologies|Technology|Systems|Solutions|"
          r"Industries|Enterprises|Stores|Motors|Airlines|Pharmaceuticals|Networks|Labs|"
          r"Laboratories|Communications|Electronics|Semiconductor|Bank|Energy|Partners")

ENTITY = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&'.\-]{1,24}\s+){0,4}(?:" + SUFFIX + r")\.?)(?![A-Za-z])")
BARE = re.compile(r"\b(Apple|Walmart|Wal-Mart|Amazon|Boeing|Costco|Target|Verizon|"
                  r"Microsoft|Intel|Nvidia|Samsung|Toyota|Ford|Nokia|Ericsson|Huawei|"
                  r"Dell|Lenovo|Sony|Siemens|Airbus|Caterpillar|Deere|Tesla|Cisco|"
                  r"Google|Foxconn|Hitachi|Fujitsu|Canon|Wistron|Avnet)\b")

# Customer grammar: the filer SELLS to the entity.
CUSTOMER_GRAMMAR = re.compile(
    r"sales?\s+to\s+|revenues?\s+from\s+|we\s+sell\s+(?:products\s+)?to\s+|"
    r"(?:largest|major|principal|significant|primary|key|top)\s+(?:customer|client)|"
    r"(?:customer|client)s?[,\s]|accounted\s+for|represented\s+", re.I)

# Supplier grammar: the entity sells to the FILER. These invert the edge, so any
# sentence carrying one is dropped rather than reversed — v1's single worst error.
SUPPLIER_GRAMMAR = re.compile(
    r"\bsupplied\b|\bsupplier|purchases?\s+from|we\s+(?:buy|purchase|source)\s+from|"
    r"\bvendor|manufactured\s+(?:for|by)\s+us|counterpart(?:y|ies)|"
    r"provided\s+to\s+us|we\s+obtain", re.I)

# The percentage must be a share of revenue, not of something else.
PCT_IS_REVENUE = re.compile(r"of\s+(?:our\s+|the\s+company'?s?\s+|total\s+|consolidated\s+|"
                            r"net\s+|annual\s+)*(?:total\s+|net\s+|consolidated\s+)*"
                            r"(?:revenue|sales|net revenue|net sales|turnover)", re.I)
PCT_NOT_REVENUE = re.compile(
    r"accounts?\s+receivable|tax\s+rate|effective\s+tax|interest\s+rate|"
    r"an?\s+increase|a\s+decrease|increased\s+by|decreased\s+by|growth|"
    r"gross\s+margin|operating\s+margin|notional|book\s+value|"
    r"of\s+(?:our\s+)?(?:total\s+)?(?:assets|equity|shares|capital|debt|backlog|"
    r"square\s+feet|employees)", re.I)

PCT = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent)")

# Page furniture and other parse artifacts.
FURNITURE = re.compile(r"table\s+of\s+contents|form\s+10-[kq]|part\s+i{1,3}\b|"
                       r"^contents\b|index\s+to|see\s+note", re.I)

NOT_A_CUSTOMER = re.compile(
    r"federal deposit|depositor[y|ies] insurance|securities investor protection|"
    r"internal revenue|financial accounting|public company accounting|"
    r"^(?:the\s+)?compan(?:y|ies)$|^group$|^systems?$|^corp(?:oration)?$|^inc$|"
    r"^holdings$|^technolog(?:y|ies)$|^solutions$|^partners$|^bank$|^limited$|^ltd$|"
    r"credit risk|cash equivalent|off-balance|united states|european union|"
    r"^(?:our|its|their|this|these|such|other|certain|various|two|three|one)\b|"
    r"generally accepted|new york stock|nasdaq stock|standard & poor|"
    r"^customer\s+group$|^contents\s+group$", re.I)

STOPWORD_START = re.compile(r"^(The|Our|Its|Their|A|An|This|That|These|Those|Such|"
                            r"Certain|Various|Other|Two|Three|One|No|Approximately|"
                            r"Additionally|However|Further|Also|In|On|At|For|With|And)\s+",
                            re.I)

# "revenues from OUR Unified Communications products" - the entity is the filer's own.
OWN_PRODUCT = re.compile(r"\b(?:our|its|the\s+company'?s?)\s+$", re.I)

SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")


def clean_entity(raw: str) -> str | None:
    s = re.sub(r"\s+", " ", raw).strip(" .,;:()[]\"'")
    prev = None
    while prev != s:
        prev = s
        s = STOPWORD_START.sub("", s).strip(" .,;:()[]\"'")
    if not s or len(s) < 4:
        return None
    if NOT_A_CUSTOMER.search(s) or FURNITURE.search(s):
        return None
    if not re.match(r"^[A-Z]", s):
        return None
    tokens = s.split()
    if len(tokens) > 7:
        return None
    core = [t for t in tokens if not re.fullmatch(r"(?:" + SUFFIX + r")\.?", t)]
    if not core and not BARE.search(s):
        return None
    return s


def self_reference(entity: str, filer_names: set[str]) -> bool:
    e = re.sub(r"[^a-z ]", "", entity.lower())
    for fn in filer_names:
        f = re.sub(r"[^a-z ]", "", fn.lower())
        if not f:
            continue
        if e.startswith(f[:12]) or f.startswith(e[:12]):
            return True
    return False


def filer_name_guess(text: str) -> set[str]:
    names = set()
    for m in re.finditer(r"\b((?:[A-Z][A-Za-z0-9&'.\-]{1,24}\s+){1,4}(?:" + SUFFIX + r")\.?)",
                         text[:6000]):
        n = m.group(1).strip()
        if len(n) > 5 and not NOT_A_CUSTOMER.search(n):
            names.add(n)
    return set(list(names)[:6])


def usable_pct(sentence: str, m: re.Match) -> bool:
    """The percentage must be a share of revenue, judged from its own neighbourhood."""
    near = sentence[max(0, m.start() - 120): m.end() + 120]
    if PCT_NOT_REVENUE.search(near):
        return False
    return bool(PCT_IS_REVENUE.search(near))


def extract_from_text(text: str, cik: str) -> list[dict]:
    filer_names = filer_name_guess(text)
    out, seen = [], set()
    for sentence in SENTENCE_SPLIT.split(text):
        if len(sentence) > 2000 or not CUSTOMER_GRAMMAR.search(sentence):
            continue
        if SUPPLIER_GRAMMAR.search(sentence):        # direction reversed - drop entirely
            continue
        pcts = [m for m in PCT.finditer(sentence)
                if THRESHOLD_PCT <= float(m.group(1)) <= 100 and usable_pct(sentence, m)]
        if not pcts:
            continue
        pct = float(pcts[0].group(1))
        cands = [m for m in ENTITY.finditer(sentence)]
        if not cands:
            cands = [m for m in BARE.finditer(sentence)]
        for m in cands:
            if OWN_PRODUCT.search(sentence[max(0, m.start() - 24): m.start()]):
                continue                              # "our <Entity> products"
            ent = clean_entity(m.group(1))
            if not ent or self_reference(ent, filer_names):
                continue
            key = (ent.lower(), round(pct, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append({"filer_cik": cik, "customer": ent, "pct": pct,
                        "context": re.sub(r"\s+", " ", sentence)[:400]})
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
    edges, with_edge = [], set()
    for cik, fname, text in filings:
        e = extract_from_text(text, cik)
        for x in e:
            x["filing"] = fname
        edges += e
        if e:
            with_edge.add(fname)
    n = len(filings)
    names = Counter(x["customer"] for x in edges)
    print(f"filings scanned          : {n}")
    print(f"filings yielding >=1 edge: {len(with_edge)}  ({len(with_edge)/n:.1%})   v1: 5.3%")
    print(f"edges                    : {len(edges)}   v1: 256")
    print(f"distinct named customers : {len(names)}   v1: 127")
    if edges:
        pcts = sorted(x["pct"] for x in edges)
        print(f"pct of sales: median {pcts[len(pcts)//2]:.1f}%  mean {sum(pcts)/len(pcts):.1f}%"
              f"   (paper: median 14.68, mean 19.80)")
        per = Counter(x["filing"] for x in edges)
        vals = sorted(per.values())
        print(f"customers per filing: median {vals[len(vals)//2]}  "
              f"mean {sum(vals)/len(vals):.2f}   (paper: median 1, mean 1.60)")
    print("\ntop customers:")
    for s, c in names.most_common(20):
        print(f"   {c:>3}  {s}")
    json.dump(edges, open(outdir / "edges_v2.json", "w"), indent=1)
    print(f"\nwrote {outdir/'edges_v2.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
