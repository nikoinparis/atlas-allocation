#!/usr/bin/env python3
"""Verify the current price block and free regime bundle as one Layer 1 bundle."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer1 import build_layer1_bundle

ROOT = Path(__file__).resolve().parents[1]
PRICE_ID = "20260812T035702Z-0c1bf62d74413e2a"
REGIME_ID = "20260812T090851Z-5c6de663ac77"
PRICE = ROOT / "data/vintages" / PRICE_ID / "payload"
REGIME = ROOT / "data/regime_vintages" / REGIME_ID / "normalized_v2"
OUTPUT = ROOT / "evidence/complete_layer1_bundle_batch_56"
CURRENT = pd.Timestamp("2026-08-07")


def dated(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def maximum_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right).abs().to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def build():
    raw = pd.read_csv(PRICE / "prices.csv", parse_dates=["observation_date"])
    prices = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    daily_log = np.log(prices.div(prices.shift(1)))
    weekly = prices.resample("W-FRI").last().loc[pd.Timestamp("2005-01-07"):CURRENT]
    actions = pd.read_csv(PRICE / "corporate_actions.csv")
    return build_layer1_bundle(
        weekly,
        daily_log_returns=daily_log,
        distribution_actions=actions,
        vix_term=dated(REGIME / "vix_term_structure.csv"),
        macro_weekly=dated(REGIME / "macro_weekly.csv"),
        google_trends=dated(REGIME / "google_trends.csv"),
    )


def main() -> int:
    first, second = build(), build()
    readiness = []
    for name, panel in first.panels.items():
        row = panel.loc[CURRENT]
        readiness.append({"input": name, "nonmissing_assets": int(row.notna().sum()), "total_assets": len(row), "current_output_available": bool(row.notna().any())})
    regime_row = first.regime_features.loc[CURRENT]
    readiness.append({"input": "regime_features", "nonmissing_assets": int(regime_row.notna().sum()), "total_assets": len(regime_row), "current_output_available": bool(regime_row.notna().any())})
    readiness_frame = pd.DataFrame(readiness)

    deterministic = []
    for name in first.panels:
        deterministic.append({"input": name, "first_hash": frame_hash(first.panels[name]), "second_hash": frame_hash(second.panels[name]), "hash_equal": frame_hash(first.panels[name]) == frame_hash(second.panels[name])})
    deterministic.append({"input": "regime_features", "first_hash": frame_hash(first.regime_features), "second_hash": frame_hash(second.regime_features), "hash_equal": frame_hash(first.regime_features) == frame_hash(second.regime_features)})
    deterministic_frame = pd.DataFrame(deterministic)

    stored_regime = dated(REGIME / "regime_features.csv")
    numeric = [name for name in stored_regime if name != "macro_regime_label_tradable"]
    difference = maximum_difference(
        first.regime_features[numeric].apply(pd.to_numeric, errors="coerce"),
        stored_regime[numeric].apply(pd.to_numeric, errors="coerce"),
    )
    built_labels = first.regime_features["macro_regime_label_tradable"].astype("string").fillna("missing")
    stored_labels = stored_regime["macro_regime_label_tradable"].astype("string").fillna("missing")
    labels_equal = built_labels.equals(stored_labels)
    ready = bool(readiness_frame.current_output_available.all() and deterministic_frame.hash_equal.all() and first.source_status["regime_features"] == "complete" and difference <= 1e-12 and labels_equal)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    readiness_frame.to_csv(OUTPUT / "current_readiness.csv", index=False)
    deterministic_frame.to_csv(OUTPUT / "determinism.csv", index=False)
    first.regime_features.tail(12).to_csv(OUTPUT / "latest_regime.csv")
    result = {
        "batch": 56,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "price_snapshot_id": PRICE_ID,
        "regime_snapshot_id": REGIME_ID,
        "market_data_through": CURRENT.date().isoformat(),
        "layer1_source_status": first.source_status,
        "all_current_outputs_available": bool(readiness_frame.current_output_available.all()),
        "all_deterministic": bool(deterministic_frame.hash_equal.all()),
        "stored_regime_rebuild_maximum_difference": difference,
        "stored_regime_labels_equal": labels_equal,
        "current_macro_risk_score": float(regime_row["macro_risk_score_tradable"]),
        "current_macro_regime_label": str(regime_row["macro_regime_label_tradable"]),
        "complete_layer1_bundle_ready": ready,
        "decision": "freeze_complete_layer1_bundle" if ready else "fail_closed",
        "forward_clock_started": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# Batch 56 — complete current Layer 1 bundle\n\n"
        f"The immutable price snapshot `{PRICE_ID}` and regime snapshot `{REGIME_ID}` were rebuilt together through {CURRENT.date()}.\n\n"
        f"Complete readiness: **{ready}**. All outputs available: **{result['all_current_outputs_available']}**. Deterministic: **{result['all_deterministic']}**. Stored-regime rebuild difference: `{difference:.3g}`.\n\n"
        f"Current regime: **{result['current_macro_regime_label']}**, macro-risk score `{result['current_macro_risk_score']:.6f}`. No forward clock or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
