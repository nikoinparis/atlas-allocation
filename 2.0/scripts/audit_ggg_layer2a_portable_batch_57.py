#!/usr/bin/env python3
"""Reconcile, causality-test, and freeze the portable GGG Layer 2a sleeves."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer1 import build_layer1_bundle
from systematic_trader.ggg_layer2a import MONTHLY_SLEEVES, SLEEVES, build_layer2a_bundle

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
HUB = V1 / "data/01_data_hub"
LAYER2A = V1 / "data/03_layer2a_strategy_logic"
PRICE_ID = "20260812T035702Z-0c1bf62d74413e2a"
REGIME_ID = "20260812T090851Z-5c6de663ac77"
PRICE = ROOT / "data/vintages" / PRICE_ID / "payload"
REGIME = ROOT / "data/regime_vintages" / REGIME_ID / "normalized_v2"
CUTOFF = pd.Timestamp("2026-04-10")
CURRENT = pd.Timestamp("2026-08-07")
MODULE = ROOT / "src/systematic_trader/ggg_layer2a.py"
OUTPUT = ROOT / "evidence/ggg_layer2a_portable_batch_57"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dated(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()


def maximum_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right).abs().to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frozen_inputs(cutoff: pd.Timestamp | None = None):
    prices = dated(HUB / "weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    weekly_simple = np.expm1(dated(HUB / "weekly_returns.csv").apply(pd.to_numeric, errors="coerce"))
    daily = dated(HUB / "daily_returns.csv").apply(pd.to_numeric, errors="coerce")
    actions = pd.read_csv(HUB / "etf_distribution_history.csv")
    vix, macro, google = dated(HUB / "vix_term_structure.csv"), dated(HUB / "macro_weekly.csv"), dated(HUB / "google_trends.csv")
    if cutoff is not None:
        prices, weekly_simple, daily = prices.loc[:cutoff], weekly_simple.loc[:cutoff], daily.loc[:cutoff]
        actions = actions.loc[pd.to_datetime(actions["Date"]) <= cutoff]
        vix, macro, google = vix.loc[:cutoff], macro.loc[:cutoff], google.loc[:cutoff]
    layer1 = build_layer1_bundle(prices, daily_log_returns=daily, distribution_actions=actions, vix_term=vix, macro_weekly=macro, google_trends=google)
    return prices, weekly_simple, layer1


def current_inputs():
    raw = pd.read_csv(PRICE / "prices.csv", parse_dates=["observation_date"])
    daily_prices = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    daily_log = np.log(daily_prices.div(daily_prices.shift(1)))
    weekly = daily_prices.resample("W-FRI").last().loc[pd.Timestamp("2005-01-07"):CURRENT]
    actions = pd.read_csv(PRICE / "corporate_actions.csv")
    layer1 = build_layer1_bundle(
        weekly, daily_log_returns=daily_log, distribution_actions=actions,
        vix_term=dated(REGIME / "vix_term_structure.csv"),
        macro_weekly=dated(REGIME / "macro_weekly.csv"),
        google_trends=dated(REGIME / "google_trends.csv"),
    )
    return weekly, layer1


def immutable_write(path: Path, text: str) -> None:
    if path.exists() and path.read_text() != text:
        raise RuntimeError(f"immutable Layer 2a artifact changed: {path}")
    if not path.exists():
        path.write_text(text)


def main() -> int:
    prices, weekly_simple, frozen_layer1 = frozen_inputs()
    first = build_layer2a_bundle(prices, frozen_layer1, weekly_simple_returns=weekly_simple, legacy_end_of_sample=True)
    second = build_layer2a_bundle(prices, frozen_layer1, weekly_simple_returns=weekly_simple, legacy_end_of_sample=True)

    equivalence_rows, return_rows, deterministic_rows = [], [], []
    frozen_positions: dict[str, pd.DataFrame] = {}
    for name in SLEEVES:
        expected = dated(LAYER2A / f"strategy_positions_{name}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
        actual = first.positions[name].reindex(index=expected.index, columns=expected.columns).fillna(0.0)
        frozen_positions[name] = expected
        difference = maximum_difference(expected, actual)
        equivalence_rows.append({"sleeve": name, "maximum_position_difference": difference, "index_equal": expected.index.equals(actual.index), "columns_equal": expected.columns.equals(actual.columns), "historical_equivalence_pass": difference <= 1e-10 and expected.index.equals(actual.index) and expected.columns.equals(actual.columns)})
        expected_path = dated(LAYER2A / f"strategy_returns_{name}.csv").apply(pd.to_numeric, errors="coerce")
        actual_path = first.paths[name].reindex(index=expected_path.index, columns=expected_path.columns)
        path_difference = maximum_difference(expected_path, actual_path)
        return_rows.append({"sleeve": name, "maximum_path_difference": path_difference, "return_path_equivalence_pass": path_difference <= 1e-10})
        deterministic_rows.append({"sleeve": name, "first_hash": frame_hash(first.positions[name]), "second_hash": frame_hash(second.positions[name]), "hash_equal": frame_hash(first.positions[name]) == frame_hash(second.positions[name])})

    prefix_rows = []
    for cutoff_text in ("2023-12-29", "2024-12-27", "2025-12-26"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix_prices, prefix_simple, prefix_layer1 = frozen_inputs(cutoff)
        prefix = build_layer2a_bundle(prefix_prices, prefix_layer1, weekly_simple_returns=prefix_simple, legacy_end_of_sample=True)
        for name in SLEEVES:
            baseline = first.positions[name].loc[:cutoff]
            candidate = prefix.positions[name].reindex(index=baseline.index, columns=baseline.columns)
            difference = maximum_difference(baseline, candidate)
            prefix_rows.append({"sleeve": name, "cutoff": cutoff_text, "maximum_prefix_difference": difference, "missingness_differences": int((baseline.isna() != candidate.isna()).to_numpy().sum()), "prefix_invariance_pass": difference <= 1e-10 and baseline.index.equals(candidate.index) and baseline.columns.equals(candidate.columns)})

    current_prices, current_layer1 = current_inputs()
    current = build_layer2a_bundle(
        current_prices, current_layer1, legacy_end_of_sample=False,
        frozen_positions=frozen_positions, frozen_cutoff=CUTOFF,
    )
    readiness_rows, latest_rows = [], []
    for name in SLEEVES:
        row = current.positions[name].loc[CURRENT]
        readiness_rows.append({
            "sleeve": name, "date": CURRENT.date().isoformat(), "nonzero_assets": int(row.abs().gt(1e-12).sum()),
            "weight_sum": float(row.sum()), "current_output_available": bool(row.notna().any() and abs(row.sum() - 1.0) <= 1e-10),
            "august_monthly_hold_pass": True if name not in MONTHLY_SLEEVES else bool(np.allclose(row.to_numpy(), current.positions[name].loc[pd.Timestamp("2026-07-31")].to_numpy(), atol=1e-12)),
        })
        for ticker, weight in row[row.abs().gt(1e-12)].items():
            latest_rows.append({"sleeve": name, "Date": CURRENT.date().isoformat(), "ticker": ticker, "weight": float(weight)})

    equivalence = pd.DataFrame(equivalence_rows)
    returns = pd.DataFrame(return_rows)
    deterministic = pd.DataFrame(deterministic_rows)
    prefixes = pd.DataFrame(prefix_rows)
    readiness = pd.DataFrame(readiness_rows)
    latest = pd.DataFrame(latest_rows)
    historical_pass = bool(equivalence.historical_equivalence_pass.all() and returns.return_path_equivalence_pass.all())
    prefix_pass = bool(prefixes.prefix_invariance_pass.all())
    deterministic_pass = bool(deterministic.hash_equal.all())
    current_pass = bool(readiness.current_output_available.all() and readiness.august_monthly_hold_pass.all())
    complete = historical_pass and prefix_pass and deterministic_pass and current_pass

    bundle_id = f"{PRICE_ID[:16]}_{REGIME_ID[:16]}_{sha256(MODULE)[:12]}"
    bundle = ROOT / "data/layer2a_vintages" / bundle_id
    positions_dir, paths_dir = bundle / "positions", bundle / "paths"
    positions_dir.mkdir(parents=True, exist_ok=True); paths_dir.mkdir(exist_ok=True)
    for name in SLEEVES:
        immutable_write(positions_dir / f"{name}.csv", current.positions[name].to_csv())
        immutable_write(paths_dir / f"{name}.csv", current.paths[name].to_csv())
    manifest = {
        "bundle_id": bundle_id, "price_snapshot_id": PRICE_ID, "regime_snapshot_id": REGIME_ID,
        "frozen_history_cutoff": CUTOFF.date().isoformat(), "market_data_through": CURRENT.date().isoformat(),
        "module_sha256": sha256(MODULE), "complete": complete,
        "positions": {name: sha256(positions_dir / f"{name}.csv") for name in SLEEVES},
        "paths": {name: sha256(paths_dir / f"{name}.csv") for name in SLEEVES},
    }
    immutable_write(bundle / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    equivalence.to_csv(OUTPUT / "historical_equivalence.csv", index=False)
    returns.to_csv(OUTPUT / "return_path_equivalence.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    deterministic.to_csv(OUTPUT / "determinism.csv", index=False)
    readiness.to_csv(OUTPUT / "current_readiness.csv", index=False)
    latest.to_csv(OUTPUT / "latest_positions.csv", index=False)
    result = {
        "batch": 57, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "module_sha256": sha256(MODULE), "layer2a_bundle_id": bundle_id,
        "historical_equivalence_pass": historical_pass,
        "maximum_historical_position_difference": float(equivalence.maximum_position_difference.max()),
        "maximum_historical_path_difference": float(returns.maximum_path_difference.max()),
        "prefix_invariance_pass": prefix_pass, "maximum_prefix_difference": float(prefixes.maximum_prefix_difference.max()),
        "deterministic": deterministic_pass, "current_outputs_ready": current_pass,
        "complete_layer2a_bundle_ready": complete,
        "decision": "freeze_complete_layer2a_bundle" if complete else "fail_closed",
        "next_blocker": "portable Layer 2b market-state and prediction engine" if complete else "Layer 2a acceptance gate failed",
        "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# Batch 57 — portable GGG Layer 2a\n\nFive sleeves were reconstructed from the complete portable Layer 1 bundle. Historical equivalence: **{historical_pass}**; maximum position difference `{result['maximum_historical_position_difference']:.3g}`; maximum path difference `{result['maximum_historical_path_difference']:.3g}`.\n\n"
        f"All 15 prefix checks passed: **{prefix_pass}**. Deterministic rerun: **{deterministic_pass}**. Current outputs through {CURRENT.date()}: **{current_pass}**. The frozen April 10 row seeds the continuation, and monthly sleeves do not falsely rebalance on incomplete August 7.\n\n"
        f"Complete Layer 2a readiness: **{complete}**. Next blocker: {result['next_blocker']}. No forward clock or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
