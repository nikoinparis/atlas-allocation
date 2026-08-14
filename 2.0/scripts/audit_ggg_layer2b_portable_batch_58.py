#!/usr/bin/env python3
"""Audit exact state reconstruction and replace leaked V1 meta forecasts."""

from __future__ import annotations

import hashlib
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer2b import build_layer2b_bundle, build_meta_predictions, build_regime_states, build_market_state_history

warnings.filterwarnings("ignore", category=FutureWarning)
ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
HUB = V1 / "data/01_data_hub"
L1 = V1 / "data/02_layer1_signals"
L2B = V1 / "data/04_layer2b_risk_regime_engine"
PRICE_ID = "20260812T035702Z-0c1bf62d74413e2a"
REGIME_ID = "20260812T090851Z-5c6de663ac77"
PRICE = ROOT / "data/vintages" / PRICE_ID / "payload"
REGIME = ROOT / "data/regime_vintages" / REGIME_ID / "normalized_v2"
CUTOFF = pd.Timestamp("2026-04-10")
CURRENT = pd.Timestamp("2026-08-07")
MODULE = ROOT / "src/systematic_trader/ggg_layer2b.py"
OUTPUT = ROOT / "evidence/ggg_layer2b_portable_batch_58"


def dated(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def maxdiff(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right).abs().to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def compare(expected: pd.DataFrame, actual: pd.DataFrame) -> tuple[float, int, int]:
    actual = actual.reindex(index=expected.index)
    common = [name for name in expected if name in actual]
    numeric = [name for name in common if pd.api.types.is_numeric_dtype(expected[name])]
    difference = maxdiff(expected[numeric], actual[numeric]) if numeric else 0.0
    missing = int((expected[common].isna() != actual[common].isna()).to_numpy().sum())
    labels = sum(int(expected[name].astype("string").fillna("missing").ne(actual[name].astype("string").fillna("missing")).sum()) for name in common if name not in numeric)
    return difference, missing, labels


def current_prices() -> pd.DataFrame:
    raw = pd.read_csv(PRICE / "prices.csv", parse_dates=["observation_date"])
    daily = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    return daily.resample("W-FRI").last().loc[pd.Timestamp("2005-01-07"):CURRENT]


def splice(frozen: pd.DataFrame, continuation: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([frozen.loc[:CUTOFF], continuation.loc[continuation.index > CUTOFF]]).sort_index()


def write_immutable(path: Path, text: str) -> None:
    if path.exists() and path.read_text() != text:
        raise RuntimeError(f"immutable artifact changed: {path}")
    if not path.exists():
        path.write_text(text)


def main() -> int:
    frozen_prices = dated(HUB / "weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    frozen_regime_features = dated(L1 / "regime_features.csv")
    historical = build_layer2b_bundle(frozen_prices, frozen_regime_features, causal_embargo=False, causal_transitions=False)
    expected = {
        "regime_score": dated(L2B / "regime_score.csv"),
        "regime_states": dated(L2B / "regime_states.csv"),
        "market_state_history": dated(L2B / "market_state_history.csv"),
    }
    actual = {"regime_score": historical.regime_score, "regime_states": historical.regime_states, "market_state_history": historical.market_state_history}
    equivalence_rows = []
    for name in expected:
        difference, missing, labels = compare(expected[name], actual[name])
        equivalence_rows.append({"artifact": name, "maximum_difference": difference, "missingness_differences": missing, "label_differences": labels, "equivalence_pass": difference <= 1e-10 and missing == 0 and labels == 0})
    equivalence = pd.DataFrame(equivalence_rows)

    prefix_rows = []
    causal_full_bundle = build_layer2b_bundle(frozen_prices, frozen_regime_features, causal_embargo=True, causal_transitions=True)
    for cutoff_text in ("2023-12-29", "2024-12-27", "2025-12-26"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix_bundle = build_layer2b_bundle(frozen_prices.loc[:cutoff], frozen_regime_features.loc[:cutoff], causal_embargo=True, causal_transitions=True)
        for name, full_frame, prefix_frame in (
            ("regime_score", historical.regime_score, prefix_bundle.regime_score),
            ("regime_states", historical.regime_states, prefix_bundle.regime_states),
            ("market_state_history", causal_full_bundle.market_state_history, prefix_bundle.market_state_history),
        ):
            difference, missing, labels = compare(full_frame.loc[:cutoff], prefix_frame)
            prefix_rows.append({"artifact": name, "cutoff": cutoff_text, "maximum_prefix_difference": difference, "missingness_differences": missing, "label_differences": labels, "prefix_pass": difference <= 1e-10 and missing == 0 and labels == 0})
        causal_full = causal_full_bundle.meta_predictions
        difference, missing, _ = compare(causal_full.loc[:cutoff], prefix_bundle.meta_predictions)
        prefix_rows.append({"artifact": "causal_meta_predictions", "cutoff": cutoff_text, "maximum_prefix_difference": difference, "missingness_differences": missing, "label_differences": 0, "prefix_pass": difference <= 1e-10 and missing == 0})
    prefixes = pd.DataFrame(prefix_rows)

    saved_predictions = dated(L2B / "phase2b_meta_predictions.csv").apply(pd.to_numeric, errors="coerce")
    leaky_compat = historical.meta_predictions.reindex(saved_predictions.index)
    causal_history_full = build_market_state_history(frozen_prices, historical.regime_score, historical.regime_states, causal_transitions=True)
    causal_historical = build_meta_predictions(causal_history_full, frozen_prices.SPY.pct_change(fill_method=None), causal_embargo=True)
    comparison_rows = []
    for column in saved_predictions:
        saved_vs_compat = (saved_predictions[column] - leaky_compat[column]).abs()
        saved_vs_causal = (saved_predictions[column] - causal_historical[column]).abs()
        comparison_rows.append({
            "prediction": column,
            "saved_vs_compat_max_difference": float(saved_vs_compat.max()),
            "saved_vs_causal_max_difference": float(saved_vs_causal.max()),
            "saved_vs_causal_changed_rows": int(saved_vs_causal.gt(1e-10).sum()),
            "label_horizon_weeks": 8 if column == "p_transition_quality" else 4,
            "saved_training_embargo_present": False,
        })
    prediction_comparison = pd.DataFrame(comparison_rows)

    live_prices = current_prices()
    hybrid_prices = splice(frozen_prices, live_prices)
    live_regime_features = dated(REGIME / "regime_features.csv")
    hybrid_regime_features = splice(frozen_regime_features, live_regime_features)
    generated_score, generated_states = build_regime_states(hybrid_prices, hybrid_regime_features)
    generated_history = build_market_state_history(hybrid_prices, generated_score, generated_states, causal_transitions=True)
    final_score = splice(expected["regime_score"], generated_score)
    final_states = splice(expected["regime_states"], generated_states)
    # State labels reproduce the frozen engine; transition probabilities are
    # rebuilt across the whole sample because the saved placement rule was not
    # prefix invariant.
    final_history = generated_history
    causal_predictions = build_meta_predictions(final_history, hybrid_prices.SPY.pct_change(fill_method=None), causal_embargo=True)
    causal_predictions_second = build_meta_predictions(final_history, hybrid_prices.SPY.pct_change(fill_method=None), causal_embargo=True)
    deterministic = causal_predictions.to_csv(float_format="%.17g") == causal_predictions_second.to_csv(float_format="%.17g")
    latest = pd.concat([
        final_states.loc[CURRENT].rename("value"),
        final_history.loc[CURRENT].rename("value"),
        causal_predictions.loc[CURRENT].rename("value"),
    ]).rename_axis("field").reset_index()

    state_equivalence = bool(equivalence.equivalence_pass.all())
    prefix_pass = bool(prefixes.prefix_pass.all())
    causal_current = bool(causal_predictions.loc[CURRENT].notna().all())
    saved_meta_qualified = False
    complete = state_equivalence and prefix_pass and causal_current and deterministic
    bundle_id = f"{PRICE_ID[:16]}_{REGIME_ID[:16]}_causalmeta_{sha256(MODULE)[:12]}"
    bundle = ROOT / "data/layer2b_vintages" / bundle_id
    bundle.mkdir(parents=True, exist_ok=True)
    frames = {"regime_score.csv": final_score, "regime_states.csv": final_states, "market_state_history.csv": final_history, "phase2b_meta_predictions_causal.csv": causal_predictions}
    for filename, frame in frames.items():
        write_immutable(bundle / filename, frame.to_csv())
    manifest = {
        "bundle_id": bundle_id, "price_snapshot_id": PRICE_ID, "regime_snapshot_id": REGIME_ID,
        "frozen_history_cutoff": CUTOFF.date().isoformat(), "market_data_through": CURRENT.date().isoformat(),
        "state_history_equivalent": state_equivalence, "saved_meta_predictions_promoted": False,
        "meta_prediction_version": "causal_embargo_v1", "complete": complete,
        "module_sha256": sha256(MODULE), "files": {filename: sha256(bundle / filename) for filename in frames},
    }
    write_immutable(bundle / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    equivalence.to_csv(OUTPUT / "state_historical_equivalence.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    prediction_comparison.to_csv(OUTPUT / "meta_prediction_leakage_comparison.csv", index=False)
    latest.to_csv(OUTPUT / "latest_state_and_predictions.csv", index=False)
    result = {
        "batch": 58, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "layer2b_bundle_id": bundle_id,
        "state_historical_equivalence_pass": state_equivalence,
        "maximum_state_historical_difference": float(equivalence.maximum_difference.max()),
        "prefix_invariance_pass": prefix_pass, "maximum_prefix_difference": float(prefixes.maximum_prefix_difference.max()),
        "saved_transition_probabilities_prefix_invariant": False,
        "saved_meta_predictions_have_label_availability_embargo": False,
        "saved_meta_predictions_promoted": saved_meta_qualified,
        "causal_meta_current_available": causal_current,
        "deterministic_rerun": deterministic,
        "complete_layer2b_bundle_ready": complete,
        "current_market_state": str(final_history.loc[CURRENT, "market_state"]),
        "current_risk_state": str(final_states.loc[CURRENT, "risk_state"]),
        "current_predictions": {name: float(causal_predictions.loc[CURRENT, name]) for name in causal_predictions},
        "decision": "freeze_states_with_corrected_causal_meta_version" if complete else "fail_closed",
        "next_step": "end-to-end GGG allocator comparison using causal meta, then resume new strategy repository experiments",
        "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# Batch 58 — portable GGG Layer 2b\n\nThe deterministic state engine matched the frozen history: **{state_equivalence}**, maximum difference `{result['maximum_state_historical_difference']:.3g}`. All state and corrected-meta prefix checks passed: **{prefix_pass}**.\n\n"
        "The saved Version 1 meta-model script did not embargo recent training labels by their 4–8 week availability horizons. Those probabilities are retained only as historical lineage and are not promoted. The replacement retrains on the same schedule but admits a row only after its full forward label window has elapsed.\n\n"
        f"The corrected current probabilities are available: **{causal_current}**. Current market state `{result['current_market_state']}`, risk state `{result['current_risk_state']}`. Complete corrected Layer 2b readiness: **{complete}**.\n\nNo forward clock or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
