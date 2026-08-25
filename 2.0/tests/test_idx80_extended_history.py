import json
from pathlib import Path

from scripts.build_idx80_extended_history_v1 import split_tickers, validate_transition


ROOT = Path(__file__).resolve().parents[1]


def test_pre2024_transition_chain_stays_at_80_and_handles_buka_fast_entry() -> None:
    config = json.loads((ROOT / "config/idx80_pre2024_history_v1.json").read_text())
    current = set(split_tickers(config["launch"]["tickers"]))
    assert len(current) == 80
    periods = [(config["launch"]["effective_from"], current.copy())]
    for transition in config["transitions"]:
        current = validate_transition(current, transition)
        periods.append((transition["effective_from"], current.copy()))
    assert all(len(members) == 80 for _, members in periods)
    before_fast = dict(periods)["2021-08-02"]
    after_fast = dict(periods)["2021-09-29"]
    assert "LINK" in before_fast and "BUKA" not in before_fast
    assert "BUKA" in after_fast and "LINK" not in after_fast


def test_pre2024_sources_are_explicitly_research_only_and_tiered() -> None:
    config = json.loads((ROOT / "config/idx80_pre2024_history_v1.json").read_text())
    assert config["research_only"] is True
    records = [config["launch"], *config["transitions"]]
    assert all(record["source_url"].startswith("https://") for record in records)
    assert all(record["evidence_tier"] for record in records)
