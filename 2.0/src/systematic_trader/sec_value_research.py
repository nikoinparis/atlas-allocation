"""Point-in-time SEC fact selection for a future survivorship-safe value sleeve."""

from __future__ import annotations

from datetime import date, timedelta


ELIGIBLE_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}


def facts_known_as_of(
    companyfacts: dict[str, object], *, taxonomy: str, concept: str, unit: str,
    decision_date: str, execution_lag_days: int = 2,
) -> list[dict[str, object]]:
    """Return only filings publicly known before the conservative decision cutoff."""
    cutoff = date.fromisoformat(decision_date) - timedelta(days=execution_lag_days)
    facts = companyfacts.get("facts", {})
    taxonomy_facts = facts.get(taxonomy, {}) if isinstance(facts, dict) else {}
    record = taxonomy_facts.get(concept, {}) if isinstance(taxonomy_facts, dict) else {}
    units = record.get("units", {}) if isinstance(record, dict) else {}
    rows = units.get(unit, []) if isinstance(units, dict) else []
    return sorted(
        [
            row for row in rows
            if row.get("filed") and date.fromisoformat(str(row["filed"])) <= cutoff
            and str(row.get("form")) in ELIGIBLE_FORMS
        ],
        key=lambda row: (str(row.get("filed", "")), str(row.get("accn", ""))),
    )


def latest_period_fact_as_of(
    companyfacts: dict[str, object], *, taxonomy: str, concept: str, unit: str,
    decision_date: str, execution_lag_days: int = 2,
) -> dict[str, object] | None:
    """Select the newest reported period, resolving amendments only when known."""
    rows = facts_known_as_of(
        companyfacts, taxonomy=taxonomy, concept=concept, unit=unit,
        decision_date=decision_date, execution_lag_days=execution_lag_days,
    )
    if not rows:
        return None
    return max(rows, key=lambda row: (str(row.get("end", "")), str(row.get("filed", "")), str(row.get("accn", ""))))
