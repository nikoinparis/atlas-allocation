"""SEC EDGAR ingestion and point-in-time XBRL normalization."""

from __future__ import annotations

import hashlib
import gzip
import json
import os
import time
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def normalize_cik(value: str | int) -> str:
    return f"{int(value):010d}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_acceptance(value: Any, filing_date: Any) -> pd.Timestamp:
    """Return a UTC availability time, conservatively falling back to filing-day end."""
    if value is not None and str(value).strip():
        parsed = pd.to_datetime(str(value), utc=True, errors="coerce")
        if pd.notna(parsed):
            return parsed
    filed = pd.to_datetime(filing_date, utc=True, errors="coerce")
    if pd.isna(filed):
        return pd.NaT
    return filed.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)


@dataclass
class SecClient:
    cache_dir: Path
    user_agent: str
    minimum_interval: float = 0.25
    timeout: int = 60
    _last_request: float = 0.0

    @classmethod
    def from_environment(cls, cache_dir: Path, *, minimum_interval: float = 0.25, timeout: int = 60) -> "SecClient":
        user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
        if not user_agent:
            raise RuntimeError(
                "Live SEC access requires SEC_USER_AGENT containing a real project/name and contact, "
                "for example: 'Portfolio Optimizer your-email@example.com'."
            )
        return cls(cache_dir=cache_dir, user_agent=user_agent, minimum_interval=minimum_interval, timeout=timeout)

    def fetch_json(self, url: str, cache_key: str) -> tuple[dict, dict]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        body_path = self.cache_dir / f"{cache_key}.json"
        metadata_path = self.cache_dir / f"{cache_key}.metadata.json"
        if body_path.exists() and metadata_path.exists():
            payload = body_path.read_bytes()
            return json.loads(payload), json.loads(metadata_path.read_text())
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type")
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()
        self._last_request = time.monotonic()
        if content_encoding == "gzip" or payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
        elif content_encoding == "deflate":
            payload = zlib.decompress(payload)
        parsed = json.loads(payload)
        metadata = {
            "url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "sha256": sha256_bytes(payload), "bytes": len(payload), "http_status": status,
            "content_type": content_type, "content_encoding": content_encoding, "cache_key": cache_key,
        }
        body_path.write_bytes(payload)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        return parsed, metadata


def ticker_mapping(payload: dict) -> pd.DataFrame:
    if "fields" in payload and "data" in payload:
        frame = pd.DataFrame(payload["data"], columns=payload["fields"])
        rename = {"cik": "cik", "name": "company_name", "ticker": "ticker", "exchange": "exchange"}
        frame = frame.rename(columns=rename)
    else:
        frame = pd.DataFrame(payload.values()).rename(columns={"cik_str": "cik", "title": "company_name"})
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["cik10"] = frame["cik"].map(normalize_cik)
    return frame[[column for column in ("ticker", "cik10", "company_name", "exchange") if column in frame]]


def _columnar_rows(payload: dict, cik10: str, source_file: str) -> list[dict]:
    columns = payload.get("filings", {}).get("recent", payload)
    if not isinstance(columns, dict) or not columns:
        return []
    count = max((len(value) for value in columns.values() if isinstance(value, list)), default=0)
    rows = []
    for index in range(count):
        row = {key: value[index] if isinstance(value, list) and index < len(value) else None for key, value in columns.items()}
        row["cik10"] = cik10
        row["source_file"] = source_file
        rows.append(row)
    return rows


def flatten_submissions(payload: dict, additional_payloads: dict[str, dict] | None = None) -> pd.DataFrame:
    cik10 = normalize_cik(payload.get("cik"))
    rows = _columnar_rows(payload, cik10, "current")
    for filename, history in (additional_payloads or {}).items():
        rows.extend(_columnar_rows(history, cik10, filename))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.rename(columns={
        "accessionNumber": "accession", "filingDate": "filing_date", "reportDate": "report_date",
        "acceptanceDateTime": "acceptance_datetime", "primaryDocument": "primary_document",
        "isXBRL": "is_xbrl", "isInlineXBRL": "is_inline_xbrl",
    })
    frame["available_at"] = [parse_acceptance(value, filed) for value, filed in zip(frame.get("acceptance_datetime"), frame.get("filing_date"))]
    for column in ("filing_date", "report_date"):
        frame[column] = pd.to_datetime(frame.get(column), errors="coerce")
    frame = frame.sort_values(["available_at", "accession"], na_position="last")
    return frame.drop_duplicates(["cik10", "accession"], keep="last").reset_index(drop=True)


def canonical_concept_map(canonical_metrics: dict[str, list[str]]) -> dict[str, tuple[str, int]]:
    mapping = {}
    for metric, concepts in canonical_metrics.items():
        for priority, concept in enumerate(concepts):
            mapping[concept] = (metric, priority)
    return mapping


def flatten_companyfacts(
    payload: dict,
    filings: pd.DataFrame,
    canonical_metrics: dict[str, list[str]],
    accepted_forms: list[str],
) -> pd.DataFrame:
    cik10 = normalize_cik(payload.get("cik"))
    concepts = canonical_concept_map(canonical_metrics)
    filing_lookup = filings.set_index("accession")["available_at"].to_dict() if not filings.empty else {}
    rows = []
    for taxonomy, taxonomy_facts in payload.get("facts", {}).items():
        for concept, detail in taxonomy_facts.items():
            if concept not in concepts:
                continue
            canonical, priority = concepts[concept]
            for unit, entries in detail.get("units", {}).items():
                for entry in entries:
                    form = str(entry.get("form", ""))
                    if form not in accepted_forms:
                        continue
                    accession = str(entry.get("accn", ""))
                    filed = entry.get("filed")
                    available = filing_lookup.get(accession)
                    if available is None or pd.isna(available):
                        available = parse_acceptance(None, filed)
                    start = pd.to_datetime(entry.get("start"), errors="coerce")
                    end = pd.to_datetime(entry.get("end"), errors="coerce")
                    rows.append({
                        "cik10": cik10, "entity_name": payload.get("entityName"), "taxonomy": taxonomy,
                        "concept": concept, "canonical_metric": canonical, "concept_priority": priority,
                        "unit": unit, "value": entry.get("val"), "start": start, "end": end,
                        "duration_days": (end - start).days if pd.notna(start) and pd.notna(end) else np.nan,
                        "accession": accession, "fiscal_year": entry.get("fy"), "fiscal_period": entry.get("fp"),
                        "form": form, "filed": pd.to_datetime(filed, errors="coerce"), "frame": entry.get("frame"),
                        "available_at": available, "is_amendment": form.endswith("/A"),
                    })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["available_at"] = pd.to_datetime(frame["available_at"], utc=True, errors="coerce")
    keys = ["cik10", "canonical_metric", "concept", "unit", "start", "end", "accession", "value"]
    return frame.sort_values(["available_at", "concept_priority"]).drop_duplicates(keys, keep="last").reset_index(drop=True)


def validate_facts(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"rows": 0, "valid": False, "reason": "no facts"}
    duplicate_keys = ["cik10", "concept", "unit", "start", "end", "accession", "value"]
    bad_availability = int(frame["available_at"].isna().sum())
    bad_period = int(((frame["start"].notna()) & (frame["end"].notna()) & (frame["start"] > frame["end"])).sum())
    return {
        "rows": len(frame), "ciks": int(frame.cik10.nunique()), "metrics": int(frame.canonical_metric.nunique()),
        "accessions": int(frame.accession.nunique()), "amendment_rows": int(frame.is_amendment.sum()),
        "duplicate_rows": int(frame.duplicated(duplicate_keys).sum()), "missing_availability": bad_availability,
        "reversed_periods": bad_period, "valid": bad_availability == 0 and bad_period == 0 and not frame.duplicated(duplicate_keys).any(),
    }


def asof_facts(facts: pd.DataFrame, decision_time: str | pd.Timestamp) -> pd.DataFrame:
    """Return the most recently accepted value for each exact fact context."""
    decision = pd.to_datetime(decision_time, utc=True)
    eligible = facts[facts.available_at < decision].copy()
    if eligible.empty:
        return eligible
    context = ["cik10", "canonical_metric", "unit", "start", "end", "fiscal_year", "fiscal_period"]
    eligible = eligible.sort_values(["available_at", "concept_priority"])
    return eligible.drop_duplicates(context, keep="last").reset_index(drop=True)


def point_in_time_event_panel(facts: pd.DataFrame, ticker_by_cik: dict[str, str]) -> pd.DataFrame:
    """Make an immutable event panel; later amendments remain separate later events."""
    columns = [
        "cik10", "canonical_metric", "value", "unit", "start", "end", "duration_days", "fiscal_year",
        "fiscal_period", "form", "accession", "filed", "available_at", "is_amendment", "concept", "concept_priority", "frame",
    ]
    panel = facts[columns].copy()
    panel.insert(1, "ticker", panel.cik10.map(ticker_by_cik))
    return panel.sort_values(["available_at", "ticker", "canonical_metric", "end"]).reset_index(drop=True)


def classify_periods(facts: pd.DataFrame) -> pd.Series:
    duration = pd.to_numeric(facts["duration_days"], errors="coerce")
    result = pd.Series("other", index=facts.index, dtype="object")
    result.loc[facts["start"].isna() & facts["end"].notna()] = "instant"
    result.loc[duration.between(60, 120)] = "quarter"
    result.loc[duration.between(121, 300)] = "year_to_date"
    result.loc[duration.between(301, 430)] = "annual"
    return result


def quarterly_factor_inputs(
    facts: pd.DataFrame,
    decisions: list[str | pd.Timestamp] | pd.DatetimeIndex,
    ticker_by_cik: dict[str, str],
) -> pd.DataFrame:
    """Create filing-time-aware raw factor inputs without cross-sectional scoring.

    Duration metrics use direct-quarter contexts only. Balance-sheet metrics use
    instantaneous contexts. Growth uses the same fiscal period from the prior
    fiscal year when that prior value was also available at the decision time.
    """
    if facts.empty:
        return pd.DataFrame()
    prepared = facts.copy()
    prepared["period_kind"] = classify_periods(prepared)
    prepared["available_at"] = pd.to_datetime(prepared["available_at"], utc=True)
    flow_metrics = {
        "revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow",
        "capital_expenditure", "share_repurchases", "stock_compensation", "diluted_shares",
    }
    balance_metrics = {"assets", "liabilities", "equity", "cash", "debt_current", "debt_noncurrent", "shares_outstanding"}
    preferred_unit = prepared.canonical_metric.map(
        lambda metric: "shares" if metric in {"shares_outstanding", "diluted_shares"} else "USD"
    )
    prepared = prepared[prepared.unit == preferred_unit].copy()
    rows = []
    for decision_value in decisions:
        decision = pd.to_datetime(decision_value, utc=True)
        eligible = prepared[prepared.available_at < decision].copy()
        eligible = eligible[
            (eligible.canonical_metric.isin(flow_metrics) & (eligible.period_kind == "quarter"))
            | (eligible.canonical_metric.isin(balance_metrics) & (eligible.period_kind == "instant"))
        ]
        if eligible.empty:
            continue
        context = ["cik10", "canonical_metric", "unit", "end", "fiscal_year", "fiscal_period"]
        eligible = eligible.sort_values(["available_at", "concept_priority"]).drop_duplicates(context, keep="last")
        for cik10, company in eligible.groupby("cik10"):
            snapshot: dict[str, Any] = {"decision_time": decision, "cik10": cik10, "ticker": ticker_by_cik.get(cik10)}
            latest_by_metric: dict[str, pd.Series] = {}
            for metric, metric_facts in company.groupby("canonical_metric"):
                latest = metric_facts.sort_values(["end", "available_at", "concept_priority"]).iloc[-1]
                latest_by_metric[metric] = latest
                snapshot[metric] = float(latest.value)
                snapshot[f"{metric}__period_end"] = latest.end
                snapshot[f"{metric}__available_at"] = latest.available_at
                if metric in flow_metrics and pd.notna(latest.fiscal_year):
                    prior = metric_facts[
                        (pd.to_numeric(metric_facts.fiscal_year, errors="coerce") == float(latest.fiscal_year) - 1)
                        & (metric_facts.fiscal_period.astype(str) == str(latest.fiscal_period))
                    ]
                    if not prior.empty:
                        prior_value = float(prior.sort_values(["available_at", "concept_priority"]).iloc[-1].value)
                        snapshot[f"{metric}__prior_year"] = prior_value
                        if abs(prior_value) > 1e-12:
                            snapshot[f"{metric}__yoy_growth"] = float(latest.value) / prior_value - 1.0
            revenue = snapshot.get("revenue")
            if revenue is not None and abs(float(revenue)) > 1e-12:
                for numerator, output in (
                    ("gross_profit", "gross_margin"), ("operating_income", "operating_margin"),
                    ("net_income", "net_margin"), ("operating_cash_flow", "operating_cash_flow_margin"),
                    ("capital_expenditure", "capital_expenditure_to_revenue"),
                    ("share_repurchases", "repurchases_to_revenue"), ("stock_compensation", "stock_compensation_to_revenue"),
                ):
                    if numerator in snapshot:
                        snapshot[output] = float(snapshot[numerator]) / float(revenue)
                if "operating_cash_flow" in snapshot and "capital_expenditure" in snapshot:
                    snapshot["free_cash_flow_margin"] = (float(snapshot["operating_cash_flow"]) - float(snapshot["capital_expenditure"])) / float(revenue)
            assets = snapshot.get("assets")
            if assets is not None and abs(float(assets)) > 1e-12:
                for numerator, output in (
                    ("liabilities", "liabilities_to_assets"), ("cash", "cash_to_assets"),
                    ("equity", "equity_to_assets"),
                ):
                    if numerator in snapshot:
                        snapshot[output] = float(snapshot[numerator]) / float(assets)
                debt = sum(float(snapshot.get(metric, 0.0)) for metric in ("debt_current", "debt_noncurrent"))
                snapshot["debt_to_assets"] = debt / float(assets)
            rows.append(snapshot)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["decision_time", "ticker"]).reset_index(drop=True)
