#!/usr/bin/env python3
"""Freeze, normalize, reconcile, and gate the first free regime-data snapshot."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_layer1 import build_regime_features
from systematic_trader.regime_data import (
    GOOGLE_KEYWORDS,
    completed_fridays,
    normalize_cboe,
    normalize_fred,
    normalize_google,
    splice_frozen_history,
)

ROOT = Path(__file__).resolve().parents[1]
V1_HUB = ROOT.parent / "1.0/data/01_data_hub"
V1_LAYER1 = ROOT.parent / "1.0/data/02_layer1_signals"
OUTPUT = ROOT / "evidence/free_regime_data_batch_55"
CUTOFF = "2026-04-10"
CURRENT_FRIDAY = "2026-08-07"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def max_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right).abs().to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def find_acquisition() -> Path:
    candidates = []
    for path in ROOT.glob("regime-snapshot.*/acquisition_metadata.json"):
        metadata = json.loads(path.read_text())
        candidates.append((metadata.get("observed_at_utc", ""), path.parent))
    if not candidates:
        raise FileNotFoundError("no regime-snapshot acquisition directory found")
    return sorted(candidates)[-1][1]


def freeze_acquisition(source: Path) -> tuple[str, Path, dict]:
    metadata = json.loads((source / "acquisition_metadata.json").read_text())
    digest = hashlib.sha256()
    for path in sorted(source.iterdir()):
        if path.is_file():
            digest.update(path.name.encode()); digest.update(path.read_bytes())
    stamp = pd.Timestamp(metadata["observed_at_utc"]).strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"{stamp}-{digest.hexdigest()[:12]}"
    payload = ROOT / "data/regime_vintages" / snapshot_id / "payload"
    if not payload.exists():
        payload.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, payload)
    return snapshot_id, payload, metadata


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def read_dated_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["Date"])
    return frame.set_index("Date").sort_index()


def write_immutable_frame(frame: pd.DataFrame, path: Path) -> None:
    text = frame.to_csv()
    if path.exists() and path.read_text() != text:
        raise RuntimeError(f"immutable normalized artifact changed: {path}")
    if not path.exists():
        path.write_text(text)


def main() -> int:
    source = find_acquisition()
    snapshot_id, payload, metadata = freeze_acquisition(source)
    index = completed_fridays("2005-01-07", CURRENT_FRIDAY)
    frozen_vix = read_dated_csv(V1_HUB / "vix_term_structure.csv")
    frozen_macro = read_dated_csv(V1_HUB / "macro_weekly.csv")
    frozen_google = read_dated_csv(V1_HUB / "google_trends.csv")
    expected_regime = read_dated_csv(V1_LAYER1 / "regime_features.csv")

    cboe = normalize_cboe(read_csv(payload / "cboe_observations.csv"), index)
    fred = normalize_fred(read_csv(payload / "fred_observations.csv"), index)
    raw_google = read_csv(payload / "google_trends_raw.csv")
    google_columns = [name for name in GOOGLE_KEYWORDS if name in raw_google]
    google_complete = metadata.get("google", {}).get("status") == "complete" and len(google_columns) == len(GOOGLE_KEYWORDS)
    google = normalize_google(raw_google, index) if google_columns else pd.DataFrame(index=index)

    overlap_end = pd.Timestamp(CUTOFF)
    vix_columns = ["VIX", "VIX3M", "VIX6M", "slope_1m_3m", "slope_1m_6m"]
    vix_rows = []
    for column in vix_columns:
        left = pd.to_numeric(frozen_vix[column], errors="coerce")
        right = pd.to_numeric(cboe[column].reindex(frozen_vix.index), errors="coerce")
        vix_rows.append({
            "column": column,
            "maximum_absolute_difference": float((left - right).abs().max()),
            "missingness_differences": int((left.isna() != right.isna()).sum()),
            "direct_source_equivalence_pass": bool((left - right).abs().max() <= 1e-8 and (left.isna() == right.isna()).all()),
        })
    vix_reconciliation = pd.DataFrame(vix_rows)

    google_rows = []
    for column in GOOGLE_KEYWORDS:
        if column not in google:
            google_rows.append({"column": column, "overlap_points": 0, "correlation": np.nan, "median_absolute_difference": np.nan, "continuity_pass": False})
            continue
        left = pd.to_numeric(frozen_google.loc[:overlap_end, column], errors="coerce")
        right = pd.to_numeric(google.reindex(left.index)[column], errors="coerce")
        pair = pd.concat([left, right], axis=1).dropna()
        correlation = float(pair.iloc[:, 0].corr(pair.iloc[:, 1])) if len(pair) >= 3 else np.nan
        median_difference = float((pair.iloc[:, 0] - pair.iloc[:, 1]).abs().median()) if len(pair) else np.nan
        google_rows.append({"column": column, "overlap_points": len(pair), "correlation": correlation, "median_absolute_difference": median_difference, "continuity_pass": bool(len(pair) >= 52 and correlation >= 0.98 and median_difference <= 2.0)})
    google_reconciliation = pd.DataFrame(google_rows)
    google_continuity_pass = bool(google_complete and google_reconciliation.continuity_pass.all())

    # Exact lineage: preserve all frozen values through the validated cutoff.
    # FRED remains supplemental because the frozen macro panel was empty.
    chained_vix = splice_frozen_history(frozen_vix, cboe, CUTOFF)
    chained_google = splice_frozen_history(frozen_google, google, CUTOFF) if google_continuity_pass else frozen_google.copy()
    historical, _ = build_regime_features(
        frozen_vix.index, vix_term=chained_vix, macro_weekly=frozen_macro, google_trends=chained_google
    )
    common = [column for column in expected_regime if column in historical]
    numeric = [column for column in common if column != "macro_regime_label_tradable"]
    historical_diff = max_difference(
        expected_regime[numeric].apply(pd.to_numeric, errors="coerce"),
        historical[numeric].apply(pd.to_numeric, errors="coerce"),
    )
    historical_missing = int((expected_regime[common].isna() != historical[common].isna()).to_numpy().sum())
    historical_pass = historical_diff <= 1e-10 and historical_missing == 0

    current_regime_ready = bool(historical_pass and google_continuity_pass and cboe.loc[pd.Timestamp(CURRENT_FRIDAY), ["VIX", "VIX3M"]].notna().all())
    if current_regime_ready:
        current_regime, _ = build_regime_features(index, vix_term=chained_vix.reindex(index), macro_weekly=frozen_macro.reindex(index), google_trends=chained_google.reindex(index))
    else:
        current_regime = pd.DataFrame(index=index)

    # Version 2 is the downstream-ready exact-lineage bundle.  The earlier
    # ``normalized`` derivation is retained immutably for audit history.
    normalized_bundle = payload.parent / "normalized_v2"
    normalized_bundle.mkdir(exist_ok=True)
    normalized_frames = {
        "vix_term_structure.csv": chained_vix.reindex(index),
        "macro_weekly.csv": frozen_macro.reindex(index),
        "google_trends.csv": chained_google.reindex(index),
        "fred_weekly_supplemental.csv": fred,
        "google_trends_candidate.csv": google,
        "regime_features.csv": current_regime,
    }
    for name, frame in normalized_frames.items():
        write_immutable_frame(frame, normalized_bundle / name)
    normalized_manifest = {
        "snapshot_id": snapshot_id,
        "frozen_history_cutoff": CUTOFF,
        "cboe_connected": True,
        "fred_connected": False,
        "google_connected": google_continuity_pass,
        "complete_regime_ready": current_regime_ready,
        "files": {name: sha256(normalized_bundle / name) for name in normalized_frames},
    }
    manifest_path = normalized_bundle / "manifest.json"
    manifest_text = json.dumps(normalized_manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text() != manifest_text:
        raise RuntimeError("immutable normalized manifest changed")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_text)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    cboe.to_csv(OUTPUT / "normalized_cboe_weekly.csv")
    fred.to_csv(OUTPUT / "normalized_fred_weekly_supplemental.csv")
    google.to_csv(OUTPUT / "normalized_google_weekly_candidate.csv")
    vix_reconciliation.to_csv(OUTPUT / "vix_source_reconciliation.csv", index=False)
    google_reconciliation.to_csv(OUTPUT / "google_source_reconciliation.csv", index=False)
    current_regime.to_csv(OUTPUT / "current_regime_features.csv")
    source_status = pd.DataFrame([
        {"source": "Cboe VIX/VIX3M/VIX6M", "acquisition_status": metadata.get("cboe", {}).get("status"), "latest_observation": metadata.get("cboe", {}).get("latest"), "role": "exact lineage continuation after frozen cutoff", "connected": True},
        {"source": "FRED", "acquisition_status": metadata.get("fred", {}).get("status"), "latest_observation": metadata.get("fred", {}).get("latest"), "role": "supplemental research only; frozen formula had no macro columns", "connected": False},
        {"source": "Google Trends via pytrends", "acquisition_status": metadata.get("google", {}).get("status"), "latest_observation": None, "role": "required exact-lineage fear component", "connected": google_continuity_pass},
    ])
    source_status.to_csv(OUTPUT / "source_status.csv", index=False)

    result = {
        "batch": 55,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "regime_snapshot_id": snapshot_id,
        "normalized_bundle": str(normalized_bundle.relative_to(ROOT)),
        "frozen_cutoff": CUTOFF,
        "current_completed_week": CURRENT_FRIDAY,
        "historical_equivalence_pass": historical_pass,
        "maximum_historical_difference": historical_diff,
        "historical_missingness_differences": historical_missing,
        "cboe_acquisition_complete": metadata.get("cboe", {}).get("status") == "complete",
        "cboe_directly_equivalent_to_yahoo_history": bool(vix_reconciliation.direct_source_equivalence_pass.all()),
        "cboe_connected_by_frozen_history_splice": True,
        "fred_acquisition_status": metadata.get("fred", {}).get("status"),
        "fred_connected_to_frozen_formula": False,
        "google_acquisition_status": metadata.get("google", {}).get("status"),
        "google_keywords_acquired": len(google_columns),
        "google_continuity_pass": google_continuity_pass,
        "current_regime_block_ready": current_regime_ready,
        "current_regime_blocker": None if current_regime_ready else "Google Trends snapshot is incomplete or fails overlap continuity; exact GGG fear component cannot be extended",
        "complete_layer1_bundle_ready": current_regime_ready,
        "decision": "freeze_complete_free_regime_bundle" if current_regime_ready else "freeze_cboe_and_fred_snapshot_fail_closed_on_google",
        "forward_clock_started": False,
        "live_trading_enabled": False,
    }
    artifacts = ["normalized_cboe_weekly.csv", "normalized_fred_weekly_supplemental.csv", "normalized_google_weekly_candidate.csv", "vix_source_reconciliation.csv", "google_source_reconciliation.csv", "current_regime_features.csv", "source_status.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifacts}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = f"""# Batch 55 — immutable free regime-data collector\n\nThe isolated Podman collector froze snapshot `{snapshot_id}`. Cboe completed through {metadata.get('cboe', {}).get('latest')}; FRED was {metadata.get('fred', {}).get('status')}; Google was {metadata.get('google', {}).get('status')} ({len(google_columns)}/4 keywords).\n\nHistorical GGG regime reconstruction passed: **{historical_pass}**, maximum difference `{historical_diff:.3g}`. Cboe is connected after the frozen 2026-04-10 history. FRED is retained for future research but is not inserted into the frozen formula.\n\nCurrent exact regime readiness: **{current_regime_ready}**. {result['current_regime_blocker'] or 'The complete block passed.'}\n\nNo forward clock or live execution was enabled.\n"""
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if historical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
