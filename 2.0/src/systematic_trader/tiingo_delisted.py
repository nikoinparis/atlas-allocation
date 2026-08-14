"""Validation helpers for Tiingo histories matched to SEC CIK identities."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


_NOISE = {
    "a", "and", "co", "company", "corp", "corporation", "de", "inc", "incorporated",
    "ltd", "llc", "lp", "plc", "the", "us", "usa",
}


def name_tokens(value: object) -> list[str]:
    words = re.findall(r"[a-z0-9]+", str(value).lower())
    return [word for word in words if word not in _NOISE and len(word) > 1]


def issuer_name_score(sec_name: object, provider_name: object) -> float:
    """Conservative blend of significant-token overlap and normalized similarity."""
    left = name_tokens(sec_name)
    right = name_tokens(provider_name)
    if not left or not right:
        return 0.0
    intersection = set(left) & set(right)
    token_score = len(intersection) / max(1, min(len(set(left)), len(set(right))))
    sequence_score = SequenceMatcher(None, " ".join(left), " ".join(right)).ratio()
    return float(max(token_score, sequence_score))


def issuer_name_match(sec_name: object, provider_name: object, threshold: float = 0.60) -> bool:
    left = set(name_tokens(sec_name))
    right = set(name_tokens(provider_name))
    if not left or not right or not (left & right):
        return False
    return issuer_name_score(sec_name, provider_name) >= threshold


def candidate_cache_key(symbol: object, cik10: object, occupied_cik10: object | None = None) -> str:
    """Keep shared/reused ticker histories separate by SEC identity when needed."""
    safe_symbol = str(symbol).replace("/", "_")
    cik = str(cik10)
    if occupied_cik10 is not None and str(occupied_cik10) != cik:
        return f"{safe_symbol}__{cik}"
    return safe_symbol
