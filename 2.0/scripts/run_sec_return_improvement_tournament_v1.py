#!/usr/bin/env python3
"""Guard the frozen eight-family tournament against premature execution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
FROZEN = ROOT / "evidence/sec_return_improvement_program_v1/frozen_config.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
PANEL_MANIFEST = ROOT / "data/sec_broad_research_panel_v1/manifest.json"
OUTPUT = ROOT / "evidence/sec_return_improvement_tournament_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authorization_state(gate: dict, config_matches_frozen: bool, panel_exists: bool) -> str:
    if not config_matches_frozen:
        return "blocked_frozen_protocol_mismatch"
    if not bool(gate.get("strategy_testing_authorized", False)):
        return "blocked_broad_research_gate"
    if not panel_exists:
        return "authorized_waiting_for_broad_panel"
    return "authorized_ready_for_frozen_tournament"


def main() -> int:
    gate = json.loads(GATE.read_text()) if GATE.exists() else {}
    config_matches = bool(CONFIG.exists() and FROZEN.exists() and sha256(CONFIG) == sha256(FROZEN))
    state = authorization_state(gate, config_matches, PANEL_MANIFEST.exists())
    result = {
        "experiment": "sec_return_improvement_tournament_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": state,
        "frozen_protocol_matches": config_matches,
        "broad_strategy_testing_authorized": bool(gate.get("strategy_testing_authorized", False)),
        "broad_panel_manifest_exists": PANEL_MANIFEST.exists(),
        "pending_tiingo_ciks": gate.get("free_tiingo_pending_ciks"),
        "minimum_decision_price_coverage": gate.get("minimum_decision_price_coverage"),
        "performance_evaluated": False,
        "performance_artifacts_written": False,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "status.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC return-improvement tournament v1\n\n"
        f"Current status: **{state}**. No broad return was calculated and no performance artifact "
        "was written. The frozen tournament can proceed only after the independent research gate "
        "authorizes it and the broad panel is materialized from validated sources. Live trading "
        "remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
