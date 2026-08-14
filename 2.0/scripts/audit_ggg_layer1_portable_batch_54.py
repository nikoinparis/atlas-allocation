#!/usr/bin/env python3
"""Reconcile the platform-owned GGG Layer 1 adapter and test current readiness."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import read_dated_csv
from systematic_trader.ggg_layer1 import build_layer1_bundle

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
LAYER1 = V1 / "data/02_layer1_signals"
HUB = V1 / "data/01_data_hub"
SNAPSHOT_ID = "20260812T035702Z-0c1bf62d74413e2a"
CURRENT = ROOT / "data/vintages" / SNAPSHOT_ID / "payload"
MODULE = ROOT / "src/systematic_trader/ggg_layer1.py"
OUTPUT = ROOT / "evidence/ggg_layer1_portable_batch_54"

EXPECTED = {
    "xsmom_global": ("signal_xsmom.csv", "xsmom_score_tradable"),
    "xsmom_raw_return_52_4w": ("signal_xsmom.csv", "xsmom_raw_return_52_4w"),
    "multi_mom_invvol": ("signal_multi_horizon_mom.csv", "multi_mom_invvol_score_tradable"),
    "residual_momentum": ("signal_residual_momentum.csv", "residual_mom_score_tradable"),
    "reversal_4w_global": ("signal_reversal.csv", "reversal_4w_score_tradable"),
    "quality_proxy": ("signal_quality.csv", "quality_score_tradable"),
    "value_proxy": ("signal_value.csv", "value_score_tradable"),
    "bab_proxy": ("signal_bab.csv", "bab_score_tradable"),
    "carry_proxy": ("signal_carry.csv", "carry_score_tradable"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_frame(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def long_panel(path: Path, value: str, index: pd.Index, columns: pd.Index) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["Date"])
    return frame.pivot(index="Date", columns="Ticker", values=value).reindex(index=index, columns=columns).rename_axis(index=None, columns=None)


def maximum_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right).abs().to_numpy()
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def missingness_difference(left: pd.DataFrame, right: pd.DataFrame) -> int:
    return int((left.isna() != right.isna()).to_numpy().sum())


def frozen_inputs():
    prices = read_dated_csv(HUB / "weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    daily = read_dated_csv(HUB / "daily_returns.csv").apply(pd.to_numeric, errors="coerce")
    actions = pd.read_csv(HUB / "etf_distribution_history.csv")
    vix = read_dated_csv(HUB / "vix_term_structure.csv")
    macro = read_dated_csv(HUB / "macro_weekly.csv")
    google = read_dated_csv(HUB / "google_trends.csv")
    return prices, daily, actions, vix, macro, google


def current_inputs():
    raw = pd.read_csv(CURRENT / "prices.csv", parse_dates=["observation_date"])
    adjusted = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    daily_log = np.log(adjusted.div(adjusted.shift(1)))
    weekly = adjusted.resample("W-FRI").last().loc[pd.Timestamp("2005-01-07"):]
    # Only completed Friday weeks may enter a decision engine.
    weekly = weekly.loc[weekly.index <= pd.Timestamp("2026-08-07")]
    actions = pd.read_csv(CURRENT / "corporate_actions.csv")
    return weekly, daily_log, actions


def build(prices, daily, actions, vix=None, macro=None, google=None):
    return build_layer1_bundle(
        prices, daily_log_returns=daily, distribution_actions=actions,
        vix_term=vix, macro_weekly=macro, google_trends=google,
    )


def main() -> int:
    prices, daily, actions, vix, macro, google = frozen_inputs()
    first = build(prices, daily, actions, vix, macro, google)
    second = build(prices, daily, actions, vix, macro, google)
    equivalence_rows = []
    for name, (filename, column) in EXPECTED.items():
        expected = long_panel(LAYER1 / filename, column, prices.index, prices.columns)
        actual = first.panels[name].reindex_like(expected)
        difference = maximum_difference(expected, actual)
        missing = missingness_difference(expected, actual)
        equivalence_rows.append({
            "input": name, "expected_file": filename, "expected_column": column,
            "maximum_absolute_difference": difference, "missingness_differences": missing,
            "tolerance": 1e-10, "equivalence_pass": difference <= 1e-10 and missing == 0,
        })
    expected_regime = read_dated_csv(LAYER1 / "regime_features.csv")
    common_regime = [column for column in expected_regime if column in first.regime_features]
    regime_expected = expected_regime[common_regime].reindex(prices.index)
    regime_actual = first.regime_features[common_regime].reindex(prices.index)
    numeric_columns = [column for column in common_regime if column != "macro_regime_label_tradable"]
    regime_difference = maximum_difference(regime_expected[numeric_columns].apply(pd.to_numeric, errors="coerce"), regime_actual[numeric_columns].apply(pd.to_numeric, errors="coerce"))
    regime_missing = missingness_difference(regime_expected, regime_actual)
    if "macro_regime_label_tradable" in common_regime:
        expected_labels = regime_expected["macro_regime_label_tradable"]
        actual_labels = regime_actual["macro_regime_label_tradable"]
        regime_label_differences = int((
            expected_labels.notna().ne(actual_labels.notna())
            | (expected_labels.notna() & actual_labels.notna() & expected_labels.ne(actual_labels))
        ).sum())
    else:
        regime_label_differences = 0
    equivalence_rows.append({
        "input": "regime_features", "expected_file": "regime_features.csv", "expected_column": "all_common_columns",
        "maximum_absolute_difference": regime_difference, "missingness_differences": regime_missing + regime_label_differences,
        "tolerance": 1e-10, "equivalence_pass": regime_difference <= 1e-10 and regime_missing + regime_label_differences == 0,
    })
    equivalence = pd.DataFrame(equivalence_rows)

    deterministic_rows = []
    for name in first.panels:
        deterministic_rows.append({"input": name, "first_hash": hash_frame(first.panels[name]), "second_hash": hash_frame(second.panels[name]), "hash_equal": hash_frame(first.panels[name]) == hash_frame(second.panels[name]), "maximum_difference": maximum_difference(first.panels[name], second.panels[name])})
    deterministic_rows.append({"input": "regime_features", "first_hash": hash_frame(first.regime_features), "second_hash": hash_frame(second.regime_features), "hash_equal": hash_frame(first.regime_features) == hash_frame(second.regime_features), "maximum_difference": maximum_difference(first.regime_features.apply(pd.to_numeric, errors="coerce"), second.regime_features.apply(pd.to_numeric, errors="coerce"))})
    deterministic = pd.DataFrame(deterministic_rows)

    prefix_rows = []
    for cutoff_text in ("2023-12-29", "2024-12-27", "2025-12-26"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix = build(prices.loc[:cutoff], daily.loc[:cutoff], actions.loc[pd.to_datetime(actions["Date"]) <= cutoff], vix.loc[:cutoff], macro.loc[:cutoff], google.loc[:cutoff])
        for name in first.panels:
            baseline = first.panels[name].loc[:cutoff]
            alternative = prefix.panels[name].reindex_like(baseline)
            prefix_rows.append({"input": name, "cutoff": cutoff_text, "maximum_prefix_difference": maximum_difference(baseline, alternative), "missingness_differences": missingness_difference(baseline, alternative)})
        baseline_regime = first.regime_features.loc[:cutoff].apply(pd.to_numeric, errors="coerce")
        alternative_regime = prefix.regime_features.reindex(baseline_regime.index).apply(pd.to_numeric, errors="coerce")
        prefix_rows.append({"input": "regime_features", "cutoff": cutoff_text, "maximum_prefix_difference": maximum_difference(baseline_regime, alternative_regime), "missingness_differences": missingness_difference(baseline_regime, alternative_regime)})
    prefix = pd.DataFrame(prefix_rows)

    current_prices, current_daily, current_actions = current_inputs()
    current_bundle = build(current_prices, current_daily, current_actions)
    current_rows = []
    for name, panel in current_bundle.panels.items():
        last = panel.loc[pd.Timestamp("2026-08-07")]
        current_rows.append({"input": name, "market_data_through": "2026-08-07", "nonmissing_assets": int(last.notna().sum()), "total_assets": len(last), "current_output_available": bool(last.notna().any())})
    current_rows.append({"input": "regime_features", "market_data_through": "2026-08-07", "nonmissing_assets": 0, "total_assets": 0, "current_output_available": False})
    current_readiness = pd.DataFrame(current_rows)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    equivalence.to_csv(OUTPUT / "historical_equivalence.csv", index=False)
    deterministic.to_csv(OUTPUT / "determinism.csv", index=False)
    prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    current_readiness.to_csv(OUTPUT / "current_readiness.csv", index=False)
    latest = pd.DataFrame({name: panel.loc[pd.Timestamp("2026-08-07")] for name, panel in current_bundle.panels.items()})
    latest.index.name = "Ticker"; latest.to_csv(OUTPUT / "current_price_signal_snapshot.csv")

    all_equivalent = bool(equivalence.equivalence_pass.all())
    all_deterministic = bool(deterministic.hash_equal.all())
    all_prefix = bool((prefix.maximum_prefix_difference <= 1e-10).all() and (prefix.missingness_differences == 0).all())
    price_inputs_ready = bool(current_readiness.loc[current_readiness.input != "regime_features", "current_output_available"].all())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 54,
        "module_sha256": sha256(MODULE), "source_snapshot_id": SNAPSHOT_ID,
        "historical_signal_inputs_tested": len(EXPECTED) + 1,
        "all_historical_equivalence_passed": all_equivalent,
        "all_deterministic": all_deterministic, "all_prefix_invariant": all_prefix,
        "maximum_historical_difference": float(equivalence.maximum_absolute_difference.max()),
        "maximum_prefix_difference": float(prefix.maximum_prefix_difference.max()),
        "current_price_and_carry_block_ready": price_inputs_ready,
        "current_regime_block_ready": False,
        "current_regime_blocker": "immutable post-April VIX term structure, macro series, and Google fear vintages are absent",
        "complete_layer1_bundle_frozen": all_equivalent and all_deterministic and all_prefix and price_inputs_ready and False,
        "decision": "freeze_partial_price_signal_adapter_fail_closed_on_regime_block" if all_equivalent and all_deterministic and all_prefix and price_inputs_ready else "adapter_reconciliation_failed",
        "forward_clock_started": False, "live_trading_enabled": False,
    }
    artifact_names = ["historical_equivalence.csv", "determinism.csv", "prefix_invariance.csv", "current_readiness.csv", "current_price_signal_snapshot.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifact_names}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if all_equivalent and all_deterministic and all_prefix and price_inputs_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
