import pandas as pd

from scripts.build_sec_broad_panel_inputs_v2 import project_path


def test_project_path_maps_container_paths_to_workspace():
    assert str(project_path("/workspace/2.0/data/example.csv")).endswith("/2.0/data/example.csv")


def test_price_signal_cutoff_is_strictly_before_decision():
    decision = pd.Timestamp("2026-04-01", tz="UTC")
    weekly = pd.date_range("2026-03-01", "2026-04-03", freq="W-FRI")
    assert weekly[weekly < decision.tz_localize(None)][-1] < decision.tz_localize(None)
