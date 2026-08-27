#!/usr/bin/env python3
"""Run the pinned upstream Kronos regression fixture in an isolated runtime."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch


SOURCE_COMMIT = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
MODEL_REVISION = "901c26c1332695a2a8f243eb2f37243a37bea320"
TOKENIZER_REVISION = "0e0117387f39004a9016484a186a908917e22426"


def load_contract(root: Path):
    path = root / "third_party_evaluation" / "adapters" / "kronos_feature_contract.py"
    spec = importlib.util.spec_from_file_location("kronos_feature_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("feature contract could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candles(frame: pd.DataFrame, timestamp_column: str) -> list[dict[str, object]]:
    result = []
    for _, row in frame.iterrows():
        item: dict[str, object] = {
            "timestamp": pd.Timestamp(row[timestamp_column]).tz_localize("UTC").isoformat()
            if pd.Timestamp(row[timestamp_column]).tzinfo is None else pd.Timestamp(row[timestamp_column]).isoformat(),
            "open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
        }
        for optional in ("volume", "amount"):
            if optional in frame.columns:
                item[optional] = float(row[optional])
        result.append(item)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    resolved = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if resolved != SOURCE_COMMIT:
        raise RuntimeError(f"checkout is not pinned: {resolved}")
    sys.path.insert(0, str(checkout))
    from model import Kronos, KronosPredictor, KronosTokenizer

    random.seed(123); np.random.seed(123); torch.manual_seed(123)
    data_root = checkout / "tests" / "data"
    source = pd.read_csv(data_root / "regression_input.csv", parse_dates=["timestamps"])
    expected_frame = pd.read_csv(data_root / "regression_output_256.csv", parse_dates=["timestamps"])
    fields = ["open", "high", "low", "close", "volume", "amount"]
    context = source.iloc[:256].copy()
    future_timestamps = source["timestamps"].iloc[256:256 + len(expected_frame)].reset_index(drop=True)
    tokenizer = KronosTokenizer.from_pretrained(
        "NeoQuasar/Kronos-Tokenizer-base", revision=TOKENIZER_REVISION
    )
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small", revision=MODEL_REVISION)
    tokenizer.eval(); model.eval()
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    with torch.no_grad():
        predicted = predictor.predict(
            df=context[fields].reset_index(drop=True),
            x_timestamp=context["timestamps"].reset_index(drop=True),
            y_timestamp=future_timestamps, pred_len=len(expected_frame),
            T=1.0, top_k=1, top_p=1.0, verbose=False, sample_count=1,
        )
    actual = predicted[fields].to_numpy(dtype=np.float32)
    expected = expected_frame[fields].to_numpy(dtype=np.float32)
    absolute = np.abs(actual - expected)
    relative = absolute / (np.abs(expected) + 1e-9)
    regression_passed = bool(np.allclose(actual, expected, rtol=1e-5))
    predicted_with_time = predicted.reset_index(drop=True).copy()
    predicted_with_time.insert(0, "timestamps", future_timestamps.reset_index(drop=True))
    contract = load_contract(Path(__file__).resolve().parents[1])
    feature = contract.materialize_forecast_features(
        candles(context, "timestamps"), [candles(predicted_with_time, "timestamps")],
        source_commit=SOURCE_COMMIT, model_revision=MODEL_REVISION,
        tokenizer_revision=TOKENIZER_REVISION,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    result = {
        "status": "passed" if regression_passed else "failed",
        "purpose": "runtime_and_feature_boundary_smoke_not_alpha_evidence",
        "source_commit": SOURCE_COMMIT, "model_revision": MODEL_REVISION,
        "tokenizer_revision": TOKENIZER_REVISION, "device": "cpu", "context_bars": 256,
        "forecast_bars": len(expected_frame), "seed": 123, "maximum_absolute_difference": float(absolute.max()),
        "maximum_relative_difference": float(relative.max()), "upstream_rtol": 1e-5,
        "regression_passed": regression_passed, "normalized_feature": feature,
        "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                    "numpy": np.__version__, "pandas": pd.__version__},
        "constraints": ["no_direct_orders", "no_host_environment_install", "requires_causal_nested_oos_alpha_test"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "regression_passed", "maximum_relative_difference", "device")}, indent=2))


if __name__ == "__main__":
    main()
