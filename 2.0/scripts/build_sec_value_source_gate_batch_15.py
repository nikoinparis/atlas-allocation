#!/usr/bin/env python3
"""Record the SEC value source decision without overstating backtest readiness."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_value_source_gate_batch_15"


def main() -> int:
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 15,
        "track": "point_in_time_value_sec",
        "source": "SEC EDGAR submissions and companyfacts REST APIs",
        "source_cost": "free; no API key",
        "source_gate": "passed_for_fact_vintages",
        "performance_test_status": "blocked_before_backtest",
        "reason": "Filing dates and accession numbers support causal fact selection, but SEC companyfacts alone does not provide historical investable-universe membership or delisting returns.",
        "implemented_controls": [
            "facts filtered by official filed date",
            "two-calendar-day conservative execution lag",
            "amended facts usable only after amendment filing date",
            "CIK retained as the intended permanent company identifier",
        ],
        "missing_controls": [
            "historical universe membership known on each decision date",
            "complete delisting returns",
            "historical security-to-company mapping across ticker changes",
            "immutable raw SEC acquisition using a user-supplied declared User-Agent",
        ],
        "decision": "build_data_foundation_but_do_not_report_value_returns_yet",
        "paid_data_required_now": False,
        "live_trading_approved": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text("\n".join([
        "# SEC Point-in-Time Value Source Gate — Batch 15", "",
        "SEC filing dates and accession numbers pass the fact-vintage gate. The platform now has tested as-of selection logic that prevents amendments or later filings from leaking backward.", "",
        "No value return, Sharpe, or drawdown is reported. SEC companyfacts does not by itself solve historical universe membership, ticker-history, or delisting-return bias, so running a current-survivor stock backtest would create false confidence.", "",
        "Decision: keep building the free data foundation; do not promote a value sleeve yet.", "",
    ]), encoding="utf-8")
    print(json.dumps({"source_gate": result["source_gate"], "performance_test_status": result["performance_test_status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
