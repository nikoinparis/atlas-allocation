import pandas as pd

import scripts.run_sec_cohort_diversified_regime_tranche_v1 as subject


def test_weighted_cohorts_add_duplicate_issuer_weights():
    choices = pd.DataFrame({
        "decision_at": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-04-01", "2025-04-01"], utc=True),
        "cik10": ["A", "B", "A", "C"],
    })
    index = pd.date_range("2025-01-03", periods=20, freq="W-FRI")
    targets = subject.weighted_cohort_targets(choices, index, [0.75, 0.25])
    latest = targets[max(targets)]
    assert abs(sum(latest.values()) - 1.0) < 1e-12
    assert latest == {"A": 0.5, "C": 0.375, "B": 0.125}


def test_first_cohort_is_normalized_without_history():
    choices = pd.DataFrame({
        "decision_at": pd.to_datetime(["2025-01-01", "2025-01-01"], utc=True),
        "cik10": ["A", "B"],
    })
    index = pd.date_range("2025-01-03", periods=3, freq="W-FRI")
    targets = subject.weighted_cohort_targets(choices, index, [0.5, 0.3, 0.2])
    assert targets[index[0]] == {"A": 0.5, "B": 0.5}
