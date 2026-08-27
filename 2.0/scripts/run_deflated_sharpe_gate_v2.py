#!/usr/bin/env python3
"""Re-run the Step 199 audit with a counted N instead of a grid.

Step 199 could not state the trial count and reported a sensitivity grid. The
ledger now holds a reconstructed lower bound of 4,412 documented configurations,
so the deflation can be computed rather than illustrated.

Two scopes are reported because the honest N depends on what you believe the
search was. Family scope asks how many configurations were tried inside the
family a book came from. Project scope asks how many were tried anywhere, which
is the right question when the book that reached a dashboard was chosen by
looking across families.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.trial_ledger import TrialLedger, deflated_sharpe  # noqa: E402

LEDGER = ROOT / "data/trial_ledger_v1/trials.jsonl"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/deflated_sharpe_gate_v2"

FAMILY_OF = {
    "150.86% Residual 1.25x": "sec_fundamental_search",
    "124% Sector Ensemble": "sec_fundamental_search",
    "142% Growth / Micron": "sec_fundamental_search",
    "102% Daily-Audited": "sec_fundamental_search",
    "ETF Incumbent": "etf_new_family_robustness",
}


def main() -> int:
    ledger = TrialLedger(LEDGER)
    verification = ledger.verify()
    if not verification["valid"]:
        raise SystemExit(f"ledger chain broken: {verification}")

    project_n = ledger.count()
    families = ledger.families()
    dashboard = json.loads(DASHBOARD.read_text())

    findings = {}
    for entry in dashboard["strategies"]:
        name = entry["strategy"]["shortName"]
        series = pd.DataFrame(entry["records"])["netReturn"].astype(float).dropna().tolist()
        family = FAMILY_OF.get(name)
        family_n = families.get(family, 0)
        findings[name] = {
            "family": family,
            "family_scope": deflated_sharpe(series, max(family_n, 2)) | {"trials_source": f"{family}={family_n}"},
            "project_scope": deflated_sharpe(series, project_n) | {"trials_source": f"all families={project_n}"},
        }

    result = {
        "experiment": "deflated_sharpe_gate_v2",
        "status": "retrospective_audit_with_counted_trials",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_verification": verification,
        "trial_counts": {"project": project_n, "by_family": families},
        "threshold": 0.95,
        "strategies": findings,
        "significant_family_scope": [
            k for k, v in findings.items() if v["family_scope"]["deflated_sharpe_ratio"] >= 0.95
        ],
        "significant_project_scope": [
            k for k, v in findings.items() if v["project_scope"]["deflated_sharpe_ratio"] >= 0.95
        ],
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"project-wide documented trials (lower bound): {project_n}\n")
    print(f"{'strategy':28s}{'annSR':>8s}{'familyN':>9s}{'DSR fam':>9s}{'DSR proj':>10s}")
    for name, f in findings.items():
        print(f"{name:28s}{f['family_scope']['annualised_sharpe']:8.2f}"
              f"{f['family_scope']['trials']:9d}"
              f"{f['family_scope']['deflated_sharpe_ratio']:9.4f}"
              f"{f['project_scope']['deflated_sharpe_ratio']:10.4f}")
    print()
    print("significant at family scope: ", result["significant_family_scope"] or "none")
    print("significant at project scope:", result["significant_project_scope"] or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
