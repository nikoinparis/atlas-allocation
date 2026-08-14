#!/usr/bin/env python3
"""Assemble and audit the first complete corrected-causal GGG engine."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
LEGACY = ROOT / "data/frozen_ggg_inputs_v1"
PRICE_ID = "20260812T035702Z-0c1bf62d74413e2a"
REGIME_ID = "20260812T090851Z-5c6de663ac77"
L2A_ID = "20260812T035702Z_20260812T090851Z_23415b848f82"
L2B_ID = "20260812T035702Z_20260812T090851Z_causalmeta_adc08ddb4c57"
PRICE = ROOT / "data/vintages" / PRICE_ID / "payload"
L2A = ROOT / "data/layer2a_vintages" / L2A_ID
L2B = ROOT / "data/layer2b_vintages" / L2B_ID
MODULE = ROOT / "src/systematic_trader/ggg_independent.py"
OUTPUT = ROOT / "evidence/ggg_end_to_end_batch_59"
CUTOFF = pd.Timestamp("2026-04-10")
CURRENT = pd.Timestamp("2026-08-07")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frame_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = (left - right.reindex_like(left)).abs().to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.max()) if finite.size else 0.0


def current_prices() -> pd.DataFrame:
    raw = pd.read_csv(PRICE / "prices.csv", parse_dates=["observation_date"])
    daily = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    return daily.resample("W-FRI").last().loc[pd.Timestamp("2005-01-07"):CURRENT]


def write_frame(path: Path, frame: pd.DataFrame) -> None:
    text = frame.to_csv()
    if path.exists() and path.read_text() != text:
        raise RuntimeError(f"immutable end-to-end input changed: {path}")
    if not path.exists():
        path.write_text(text)


def assemble(prices: pd.DataFrame) -> tuple[str, Path]:
    fingerprints = "".join([PRICE_ID, REGIME_ID, L2A_ID, L2B_ID, sha256(MODULE)])
    bundle_id = "ggg_causal_v2_" + hashlib.sha256(fingerprints.encode()).hexdigest()[:16]
    bundle = ROOT / "data/ggg_vintages" / bundle_id
    hub = bundle / "data/01_data_hub"; layer2a = bundle / "data/03_layer2a_strategy_logic"; layer2b = bundle / "data/04_layer2b_risk_regime_engine"
    for directory in (hub, layer2a, layer2b): directory.mkdir(parents=True, exist_ok=True)
    write_frame(hub / "weekly_prices.csv", prices)
    for name in ("dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "taa_10m_sma", "composite_regime_conditioned"):
        position = read_dated_csv(L2A / f"positions/{name}.csv")
        path = read_dated_csv(L2A / f"paths/{name}.csv")
        write_frame(layer2a / f"strategy_positions_{name}.csv", position)
        write_frame(layer2a / f"strategy_returns_{name}.csv", path)
    for source, target in (
        ("market_state_history.csv", "market_state_history.csv"),
        ("regime_states.csv", "regime_states.csv"),
        ("phase2b_meta_predictions_causal.csv", "phase2b_meta_predictions.csv"),
    ):
        write_frame(layer2b / target, read_dated_csv(L2B / source))
    files = sorted(path for path in bundle.rglob("*.csv"))
    manifest = {
        "bundle_id": bundle_id, "engine_version": "ggg_causal_v2", "market_data_through": CURRENT.date().isoformat(),
        "price_snapshot_id": PRICE_ID, "regime_snapshot_id": REGIME_ID, "layer2a_bundle_id": L2A_ID, "layer2b_bundle_id": L2B_ID,
        "allocator_module_sha256": sha256(MODULE), "legacy_terminal_rebalance": False,
        "files": {str(path.relative_to(bundle)): sha256(path) for path in files},
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path = bundle / "manifest.json"
    if path.exists() and path.read_text() != text: raise RuntimeError("immutable GGG manifest changed")
    if not path.exists(): path.write_text(text)
    return bundle_id, bundle


def metrics(path: pd.DataFrame) -> dict:
    returns = pd.to_numeric(path.net_return, errors="coerce").dropna()
    turnover = pd.to_numeric(path.turnover, errors="coerce").reindex(returns.index)
    wealth = (1 + returns).cumprod(); years = len(returns) / 52
    arithmetic = float(returns.mean() * 52); vol = float(returns.std(ddof=1) * np.sqrt(52))
    downside = float(np.sqrt(returns.clip(upper=0).pow(2).mean()) * np.sqrt(52))
    drawdown = wealth / wealth.cummax() - 1
    return {"weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()), "cagr": float(wealth.iloc[-1] ** (1 / years) - 1), "arithmetic_ann_return": arithmetic, "ann_vol": vol, "sharpe_zero_rf": arithmetic / vol if vol else np.nan, "sortino_zero_target": arithmetic / downside if downside else np.nan, "max_drawdown": float(drawdown.min()), "annual_one_way_turnover": float(turnover.mean() * 52)}


def windows(path: pd.DataFrame) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {"full": path, "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)], "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)], "trailing_3y": path.loc[path.index >= end - pd.DateOffset(years=3)], "post_2024": path.loc[path.index >= pd.Timestamp("2024-01-05")]}


def main() -> int:
    prices = current_prices(); bundle_id, bundle = assemble(prices)
    corrected = run_from_artifacts(bundle, causal_training=True, legacy_terminal_rebalance=False)
    repeated = run_from_artifacts(bundle, causal_training=True, legacy_terminal_rebalance=False)
    deterministic = all(frame_hash(corrected.stages[name]) == frame_hash(repeated.stages[name]) for name in corrected.stages)
    current_weights = corrected.stages["final_etf_weights"].loc[CURRENT]
    current_sleeves = corrected.stages["final_sleeve_weights"].loc[CURRENT]
    july_sleeves = corrected.stages["final_sleeve_weights"].loc[pd.Timestamp("2026-07-31")]
    # ETF look-through may still move because CTA is a weekly sleeve.  The
    # calendar gate applies to the top-level monthly sleeve allocation.
    august_hold = bool(np.allclose(current_sleeves.to_numpy(), july_sleeves.to_numpy(), atol=1e-12))
    august_not_in_rebalance_log = CURRENT not in corrected.audit_log.index

    frozen_prices = read_dated_csv(V1 / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    legacy_result = run_from_artifacts(LEGACY, prices_override=frozen_prices, causal_training=True, legacy_terminal_rebalance=True)
    corrected_frozen = run_from_artifacts(bundle, prices_override=frozen_prices, causal_training=True, legacy_terminal_rebalance=True)
    performance_rows = []
    for implementation, weights, sample_prices in (
        ("legacy_saved_meta", legacy_result.stages["final_etf_weights"], frozen_prices),
        ("corrected_causal_same_history", corrected_frozen.stages["final_etf_weights"], frozen_prices),
        ("corrected_causal_current", corrected.stages["final_etf_weights"], prices),
    ):
        forward = next_week_returns(sample_prices)
        for cost in (10, 50, 100):
            path = portfolio_path(weights, forward, float(cost))
            for window, subset in windows(path).items():
                performance_rows.append({"implementation": implementation, "cost_bps": cost, "window": window, **metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix_result = run_from_artifacts(bundle, prices_override=prices.loc[:cutoff], causal_training=True, legacy_terminal_rebalance=False)
        for stage in corrected.stages:
            baseline = corrected.stages[stage].loc[:cutoff]
            candidate = prefix_result.stages[stage].reindex_like(baseline)
            prefix_rows.append({"stage": stage, "cutoff": cutoff_text, "maximum_prefix_difference": frame_difference(baseline, candidate), "prefix_pass": frame_difference(baseline, candidate) <= 1e-10})
    prefixes = pd.DataFrame(prefix_rows)

    legacy_current_date = CUTOFF
    allocation_difference = frame_difference(legacy_result.stages["final_etf_weights"], corrected_frozen.stages["final_etf_weights"])
    changed_rows = int((legacy_result.stages["final_etf_weights"] - corrected_frozen.stages["final_etf_weights"]).abs().max(axis=1).gt(1e-10).sum())
    complete = deterministic and bool(prefixes.prefix_pass.all()) and august_hold and august_not_in_rebalance_log and abs(float(current_weights.sum()) - 1) <= 1e-10
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False); prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    current_weights[current_weights.gt(1e-12)].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "current_holdings.csv")
    corrected.audit_log.tail(12).to_csv(OUTPUT / "latest_allocator_audit.csv")
    result = {
        "batch": 59, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "ggg_bundle_id": bundle_id,
        "complete_end_to_end_ready": complete, "deterministic": deterministic,
        "prefix_invariance_pass": bool(prefixes.prefix_pass.all()), "maximum_prefix_difference": float(prefixes.maximum_prefix_difference.max()),
        "incomplete_august_terminal_rebalance_prevented": august_hold,
        "august_absent_from_monthly_rebalance_log": august_not_in_rebalance_log,
        "current_weight_sum": float(current_weights.sum()), "current_nonzero_holdings": int(current_weights.gt(1e-12).sum()),
        "legacy_vs_corrected_maximum_weight_difference": allocation_difference, "legacy_vs_corrected_changed_rows": changed_rows,
        "decision": "freeze_clean_ggg_causal_v2_benchmark" if complete else "fail_closed",
        "new_strategy_research_ready": complete,
        "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    same = performance[(performance.implementation == "corrected_causal_same_history") & (performance.cost_bps == 50) & (performance.window == "trailing_3y")].iloc[0]
    old = performance[(performance.implementation == "legacy_saved_meta") & (performance.cost_bps == 50) & (performance.window == "trailing_3y")].iloc[0]
    current = performance[(performance.implementation == "corrected_causal_current") & (performance.cost_bps == 50) & (performance.window == "trailing_3y")].iloc[0]
    (OUTPUT / "report.md").write_text(
        f"# Batch 59 — complete corrected-causal GGG\n\nEnd-to-end readiness: **{complete}**. Deterministic: **{deterministic}**. All {len(prefixes)} stage-prefix checks passed: **{bool(prefixes.prefix_pass.all())}**, maximum difference `{prefixes.maximum_prefix_difference.max():.3g}`. August terminal rebalance prevented: **{august_hold}**.\n\n"
        f"At 50 bps on the common frozen history, trailing-three-year legacy CAGR/Sharpe/drawdown were `{old.cagr:.2%}` / `{old.sharpe_zero_rf:.3f}` / `{old.max_drawdown:.2%}`. Corrected-causal values were `{same.cagr:.2%}` / `{same.sharpe_zero_rf:.3f}` / `{same.max_drawdown:.2%}`. Extended through current data, corrected-causal trailing-three-year values are `{current.cagr:.2%}` / `{current.sharpe_zero_rf:.3f}` / `{current.max_drawdown:.2%}`.\n\n"
        f"The correction changed {changed_rows} historical final-weight rows, with maximum asset-weight difference `{allocation_difference:.4f}`. This corrected engine is the new research benchmark; it is not a guarantee of future profit. No forward clock or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
