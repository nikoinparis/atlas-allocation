"""Point-in-time historical filer-universe construction from SEC FSDS SUB rows."""

from __future__ import annotations

from collections.abc import Iterable
import html
import re

import pandas as pd


_TAG_RE = re.compile(r"<[^>]+>")
_SYMBOL_RE = re.compile(r"^(?=[A-Z0-9.\-]*[A-Z])[A-Z0-9][A-Z0-9.\-]{0,11}$")


def extract_trading_symbols(document: str | bytes) -> list[str]:
    """Extract explicitly XBRL-tagged cover-page symbols without guessing from names."""
    if isinstance(document, bytes):
        text = document.decode("utf-8", errors="ignore")
    else:
        text = document
    patterns = [
        r"<ix:nonNumeric\b[^>]*\bname=[\"']dei:(?:Entity)?TradingSymbol[\"'][^>]*>(.*?)</ix:nonNumeric>",
        r"<dei:(?:Entity)?TradingSymbol\b[^>]*>(.*?)</dei:(?:Entity)?TradingSymbol>",
    ]
    values: list[str] = []
    for pattern in patterns:
        for raw in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            value = html.unescape(_TAG_RE.sub("", raw)).strip().upper()
            if _SYMBOL_RE.fullmatch(value) and value not in values:
                values.append(value)
    return values


def sic_sector(sic: object, groups: dict[str, list[list[int]]]) -> str | None:
    """Map an as-filed SIC to the first explicitly declared sector range."""
    try:
        value = int(float(sic))
    except (TypeError, ValueError):
        return None
    for sector, ranges in groups.items():
        if any(int(low) <= value <= int(high) for low, high in ranges):
            return sector
    return None


def normalize_submissions(
    frame: pd.DataFrame,
    sic_groups: dict[str, list[list[int]]],
    accepted_forms: Iterable[str],
    accepted_filer_statuses: Iterable[str],
) -> pd.DataFrame:
    """Normalize and filter SEC SUB records without using present-day identity data."""
    required = {"adsh", "cik", "name", "sic", "form", "filed", "accepted", "afs"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"SEC SUB data missing columns: {missing}")
    result = frame.copy()
    result["form"] = result["form"].astype(str).str.strip().str.upper()
    result["afs"] = result["afs"].fillna("").astype(str).str.strip().str.upper()
    result = result[result["form"].isin({str(x).upper() for x in accepted_forms})]
    result = result[result["afs"].isin({str(x).upper() for x in accepted_filer_statuses})]
    result["sector"] = result["sic"].map(lambda value: sic_sector(value, sic_groups))
    result = result[result["sector"].notna()].copy()
    result["cik10"] = pd.to_numeric(result["cik"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    accepted_text = result["accepted"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    result["available_at"] = pd.to_datetime(accepted_text, format="%Y%m%d%H%M%S", utc=True, errors="coerce")
    filed = pd.to_datetime(result["filed"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True), format="%Y%m%d", utc=True, errors="coerce")
    result["available_at"] = result["available_at"].fillna(filed + pd.Timedelta(days=1))
    result["filing_date"] = filed.dt.tz_localize(None)
    result["sic"] = pd.to_numeric(result["sic"], errors="coerce").astype("Int64")
    result["company_name_as_filed"] = result["name"].astype(str).str.strip()
    keep = [
        "adsh", "cik10", "company_name_as_filed", "sic", "sector", "form", "afs",
        "filing_date", "available_at", "period", "fy", "fp", "source_quarter",
    ]
    for column in keep:
        if column not in result:
            result[column] = pd.NA
    result = result[keep].dropna(subset=["available_at"])
    return result.sort_values(["available_at", "adsh"]).drop_duplicates("adsh", keep="last").reset_index(drop=True)


def quarter_decisions(start: object, end: object) -> pd.DatetimeIndex:
    """UTC decision instants immediately after each completed calendar quarter."""
    starts = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="QE")
    return pd.DatetimeIndex(starts.tz_localize("UTC") + pd.Timedelta(days=1))


def build_membership(
    submissions: pd.DataFrame,
    decisions: Iterable[object],
    staleness_days: int = 450,
) -> pd.DataFrame:
    """Select the latest filing known strictly before each decision for every CIK."""
    frames: list[pd.DataFrame] = []
    ordered = submissions.sort_values(["available_at", "adsh"])
    for value in decisions:
        decision = pd.Timestamp(value)
        if decision.tzinfo is None:
            decision = decision.tz_localize("UTC")
        else:
            decision = decision.tz_convert("UTC")
        eligible = ordered[ordered["available_at"] < decision]
        if eligible.empty:
            continue
        latest = eligible.drop_duplicates("cik10", keep="last").copy()
        latest["filing_age_days"] = (decision - latest["available_at"]).dt.total_seconds() / 86400.0
        latest = latest[latest["filing_age_days"] <= int(staleness_days)].copy()
        latest.insert(0, "decision_at", decision)
        frames.append(latest)
    if not frames:
        return pd.DataFrame(columns=["decision_at", *submissions.columns, "filing_age_days"])
    return pd.concat(frames, ignore_index=True).sort_values(["decision_at", "sector", "cik10"]).reset_index(drop=True)


def attach_current_tickers(membership: pd.DataFrame, mapping: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach current identifiers only as coverage metadata, never as membership input."""
    current = mapping.copy()
    current["cik10"] = pd.to_numeric(current["cik"], errors="coerce").astype("Int64").astype(str).str.zfill(10)
    current["ticker"] = current["ticker"].astype(str).str.upper().str.strip()
    grouped = current.groupby("cik10", as_index=False).agg(
        current_tickers=("ticker", lambda values: "|".join(sorted(set(values)))),
        current_exchanges=("exchange", lambda values: "|".join(sorted({str(x) for x in values if pd.notna(x)}))),
    )
    unique_ciks = membership[["cik10", "company_name_as_filed", "sector"]].drop_duplicates("cik10", keep="last")
    identities = unique_ciks.merge(grouped, on="cik10", how="left")
    identities["has_current_sec_ticker"] = identities["current_tickers"].notna()
    identities["identity_status"] = identities["has_current_sec_ticker"].map({True: "current_ticker_available", False: "former_or_unmapped"})
    attached = membership.merge(identities[["cik10", "current_tickers", "current_exchanges", "identity_status"]], on="cik10", how="left")
    return attached, identities.sort_values(["identity_status", "sector", "cik10"]).reset_index(drop=True)
