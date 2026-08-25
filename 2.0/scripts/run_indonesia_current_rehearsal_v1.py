#!/usr/bin/env python3
"""Materialize a research-only Indonesian current-universe strategy rehearsal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.indonesia_equity import (  # noqa: E402
    IndonesiaResearchSpec,
    RESEARCH_ONLY_NOTICE,
    build_research_target,
)
from src.systematic_trader.indonesia_rehearsal import build_weekly_feature_snapshot  # noqa: E402


DATA_ROOT = ROOT / "data" / "indonesia_equity_vintages"
OUTPUT_ROOT = ROOT / "evidence" / "indonesia_current_rehearsal_v1"
CONFIG = ROOT / "config" / "indonesia_equity_research_v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_input_vintage(vintage: Path, manifest: dict[str, object]) -> None:
    for name, metadata in manifest["files"].items():
        path = vintage / name
        if not path.is_file() or sha256(path) != metadata["sha256"]:
            raise ValueError(f"input vintage hash mismatch: {name}")
    claims = manifest["claims"]
    forbidden = ("backtest_authorized", "performance_claim_authorized", "live_trading_enabled")
    if any(claims.get(name) is not False for name in forbidden):
        raise ValueError("input vintage is not locked to research-only use")


def markdown_table(target: pd.DataFrame) -> str:
    selected = target[target["ticker"] != "CASH_IDR"].copy()
    lines = [
        "| Ticker | Research weight | Score | 52w momentum, skip 4w | 26w volatility | Median daily value |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in selected.itertuples(index=False):
        lines.append(
            f"| {row.ticker} | {row.research_weight:.2%} | {row.research_score:.3f} | "
            f"{row.momentum_52w_skip_4w:.2%} | {row.volatility_26w:.2%} | "
            f"IDR {row.median_daily_value_idr / 1_000_000_000:.1f}bn |"
        )
    return "\n".join(lines)


def main() -> None:
    vintage_id = (DATA_ROOT / "LATEST").read_text(encoding="utf-8").strip()
    vintage = DATA_ROOT / vintage_id
    input_manifest = json.loads((vintage / "manifest.json").read_text(encoding="utf-8"))
    verify_input_vintage(vintage, input_manifest)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    strategy = config["strategy"]
    spec = IndonesiaResearchSpec(
        universe=config["primary_universe"],
        top_n=int(strategy["selection_count"]),
        minimum_eligible_names=int(strategy["minimum_eligible_names"]),
        maximum_name_weight=float(strategy["maximum_name_weight"]),
        minimum_median_daily_value_idr=float(strategy["minimum_median_daily_value_idr"]),
        momentum_weight=float(strategy["signal"]["momentum_52w_skip_4w_weight"]),
        low_volatility_weight=float(strategy["signal"]["low_volatility_26w_weight"]),
    )

    prices = pd.read_csv(vintage / "prices.csv")
    membership = pd.read_csv(vintage / "universe_membership.csv")
    idx80 = sorted(set(membership.loc[membership["universe"] == "IDX80", "ticker"]))
    known_at = pd.Timestamp(input_manifest["observed_at_utc"])
    decision_at = pd.Timestamp(input_manifest["created_at_utc"]) + pd.Timedelta(seconds=1)
    features, exclusions, weekly = build_weekly_feature_snapshot(
        prices, known_at=known_at, universe_tickers=idx80
    )
    liquidity_exclusions = features[
        features["median_daily_value_idr"] < spec.minimum_median_daily_value_idr
    ][["ticker", "median_daily_value_idr"]].copy()
    if not liquidity_exclusions.empty:
        liquidity_exclusions["reason"] = "below_minimum_liquidity"
        liquidity_exclusions["minimum_median_daily_value_idr"] = (
            spec.minimum_median_daily_value_idr
        )
        exclusions = pd.concat([exclusions, liquidity_exclusions], ignore_index=True).sort_values(
            ["reason", "ticker"]
        )
    target, diagnostics = build_research_target(
        features, membership, decision_at=decision_at, spec=spec
    )
    target = target.merge(
        features[["ticker", "price_observation_date", "weekly_observations"]],
        on="ticker",
        how="left",
    )

    run_id = f"{pd.Timestamp(input_manifest['created_at_utc']).strftime('%Y%m%dT%H%M%SZ')}-current-snapshot-v1"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_ROOT / run_id
    if destination.exists():
        raise FileExistsError(f"rehearsal already exists: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=OUTPUT_ROOT))
    try:
        weekly.to_csv(staging / "weekly_prices.csv", index=False)
        features.to_csv(staging / "features.csv", index=False)
        exclusions.to_csv(staging / "exclusions.csv", index=False)
        target.to_csv(staging / "research_target.csv", index=False)

        diagnostics.update(
            {
                "input_vintage_id": vintage_id,
                "known_at": known_at.isoformat(),
                "daily_price_through": str(prices["observation_date"].max()),
                "current_idx80_members": len(idx80),
                "feature_rows": len(features),
                "excluded_names": len(exclusions),
                "excluded_for_feature_history": int(
                    exclusions["reason"].eq("insufficient_weekly_history").sum()
                ),
                "excluded_for_liquidity": int(
                    exclusions["reason"].eq("below_minimum_liquidity").sum()
                ),
                "performance_metrics_calculated": False,
                "return_path_calculated": False,
                "benchmark_performance_calculated": False,
                "recommendation_authorized": False,
            }
        )
        (staging / "diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        blockers = [name for name, passed in config["source_gates"].items() if not passed]
        report = f"""# Indonesia Current-Universe Research Rehearsal v1

> **{RESEARCH_ONLY_NOTICE}**

This is a single, dated rehearsal using the **current IDX80 snapshot** observed on
{known_at.date().isoformat()}. It does not calculate a historical return path,
benchmark performance, expected return, or investability conclusion.

## Snapshot controls

- Input vintage: `{vintage_id}`
- Daily observations through: {prices['observation_date'].max()}
- Feature knowledge cutoff: {known_at.isoformat()}
- Model decision time: {decision_at.isoformat()}
- Current IDX80 members supplied: {len(idx80)}
- Feature-complete names: {len(features)}
- Names excluded for insufficient feature history: {diagnostics['excluded_for_feature_history']}
- Names excluded by the liquidity floor: {diagnostics['excluded_for_liquidity']}
- Eligible after the IDR {spec.minimum_median_daily_value_idr / 1_000_000_000:.1f}bn liquidity floor: {diagnostics['eligible_feature_rows']}
- Selected research candidates: {diagnostics['selected_names']}
- Execution authorized: **No**

## Candidate snapshot

{markdown_table(target)}

Weights are capped inverse-volatility **research weights**. Scores combine 70%
cross-sectional 52-week momentum excluding the most recent four weeks and 30%
low 26-week volatility. Liquidity is the median daily close times volume over
the latest 63 actual trading observations. These candidates are not buy calls.

## Evidence limits

The list uses constituent membership acquired in August 2026 only at this one
decision time. It must never be backfilled into earlier dates. Price history is
a frozen Yahoo Finance research cache and may contain vendor revisions. The
official IDX constituent file has not been validated, inactive/delisted-security
coverage is incomplete, and redistribution rights are not asserted.

Open source gates: {', '.join(blockers)}.

Before any investable or startup-facing product, acquire licensed point-in-time
membership and prices, validate corporate actions and inactive securities, add
Indonesia-specific fees/taxes/spreads, complete company-level valuation,
governance and catalyst diligence, and obtain Indonesian legal/OJK review.
"""
        (staging / "report.md").write_text(report, encoding="utf-8")

        output_names = [
            "weekly_prices.csv",
            "features.csv",
            "exclusions.csv",
            "research_target.csv",
            "diagnostics.json",
            "report.md",
        ]
        result_manifest = {
            "run_id": run_id,
            "purpose": "research-only current-universe Indonesian strategy rehearsal",
            "notice": RESEARCH_ONLY_NOTICE,
            "input_vintage_id": vintage_id,
            "input_manifest_sha256": sha256(vintage / "manifest.json"),
            "config_sha256": sha256(CONFIG),
            "program_sha256": sha256(Path(__file__)),
            "known_at": known_at.isoformat(),
            "decision_at": decision_at.isoformat(),
            "claims": {
                "historical_backtest": False,
                "performance_metrics_calculated": False,
                "return_path_calculated": False,
                "investment_recommendation": False,
                "execution_authorized": False,
                "current_snapshot_only": True,
            },
            "outputs": {
                name: {"bytes": (staging / name).stat().st_size, "sha256": sha256(staging / name)}
                for name in output_names
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(result_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        staging.rename(destination)
        (OUTPUT_ROOT / "LATEST").write_text(run_id + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    print(json.dumps({"output": str(destination), "diagnostics": diagnostics}, indent=2))


if __name__ == "__main__":
    main()
