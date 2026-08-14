#!/usr/bin/env python3
"""Discover independent causal sources that can improve the aggressive xsmom ceiling."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.independent_return_sources import monthly_weights, signal_families
from systematic_trader.residual_momentum_source import residual_momentum_signal

CONFIG_PATH = ROOT / "config/independent_return_source_discovery_batch_63.json"
OUTPUT = ROOT / "evidence/independent_return_source_discovery_batch_63"
PRICE_BUNDLE = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a"
CEILING_WEIGHTS = ROOT / "evidence/aggressive_return_discovery_batch_62/selected_candidate_weights.csv"


def build_sources(prices: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    panels = signal_families(prices)
    panels["residual_momentum"] = residual_momentum_signal(prices)
    result = {}
    for family in config["source_families"]:
        for top_n in config["top_n"]:
            name = f"{family}_top{top_n}"
            result[name] = monthly_weights(
                panels[family], prices, config["discovery_assets"], top_n=int(top_n),
                method=config["source_method"], minimum_score=0.05,
            )
    return result


def correlation(left: pd.Series, right: pd.Series) -> float:
    frame = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    return float(frame.corr().iloc[0, 1])


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    prices = read_dated_csv(PRICE_BUNDLE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    ceiling = read_dated_csv(CEILING_WEIGHTS).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    sources = build_sources(prices, config)
    repeated = build_sources(prices, config)
    deterministic = all(batch60.frame_hash(frame) == batch60.frame_hash(repeated[name]) for name, frame in sources.items())
    expected_sources = len(config["source_families"]) * len(config["top_n"])
    expected_blends = expected_sources * len(config["blend_weights"])
    if len(sources) != expected_sources:
        raise RuntimeError("source budget mismatch")

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix = build_sources(prices.loc[:cutoff], config)
        for name, full in sources.items():
            expected = full.loc[:cutoff]
            actual = prefix[name].reindex_like(expected)
            difference = float((expected - actual).abs().max().max())
            prefix_rows.append({"source": name, "cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)

    candidates = {"aggressive_ceiling": ceiling}
    for source, weights in sources.items():
        candidates[f"standalone::{source}"] = weights
        for alpha in config["blend_weights"]:
            candidates[f"blend::{source}::{alpha:.1f}"] = mix([ceiling, weights], [1.0 - alpha, alpha])

    paths, performance_rows = {}, []
    for name, weights in candidates.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][int(cost)] = path
            for window, subset in batch60.windows(path).items():
                performance_rows.append({"candidate": name, "cost_bps": cost, "window": window, **batch60.metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    def row(name: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.candidate == name) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    ceiling_rows = {key: row("aggressive_ceiling", key, 50) for key in ("trailing_1y", "trailing_2y", "trailing_3y", "full")}
    ceiling100 = row("aggressive_ceiling", "trailing_3y", 100)
    standalone_rows = []
    source_pass = {}
    for source in sources:
        name = f"standalone::{source}"
        recent, recent100, full = row(name, "trailing_3y", 50), row(name, "trailing_3y", 100), row(name, "full", 50)
        corr = correlation(paths[name][50].net_return, paths["aggressive_ceiling"][50].net_return)
        rules = config["standalone_gates"]
        checks = {
            "recent_return": recent.cagr >= rules["minimum_trailing_3y_50bps_cagr"],
            "cost_stress": recent100.cagr >= rules["minimum_trailing_3y_100bps_cagr"],
            "full_return": full.cagr >= rules["minimum_full_50bps_cagr"],
            "correlation": abs(corr) <= rules["maximum_full_correlation_to_ceiling"],
            "drawdown": abs(recent.max_drawdown) <= rules["maximum_recent_drawdown_magnitude"],
        }
        source_pass[source] = all(checks.values())
        standalone_rows.append({"source": source, "trailing_3y_50bps_cagr": recent.cagr, "trailing_3y_50bps_sharpe": recent.sharpe_zero_rf, "trailing_3y_100bps_cagr": recent100.cagr, "full_50bps_cagr": full.cagr, "recent_drawdown": recent.max_drawdown, "full_correlation_to_ceiling": corr, **{f"gate_{key}": value for key, value in checks.items()}, "qualified": all(checks.values())})
    standalone = pd.DataFrame(standalone_rows).sort_values(["qualified", "trailing_3y_50bps_cagr"], ascending=False)

    blend_rows = []
    for source in sources:
        for alpha in config["blend_weights"]:
            name = f"blend::{source}::{alpha:.1f}"
            r1, r2, r3, r100, full = row(name, "trailing_1y", 50), row(name, "trailing_2y", 50), row(name, "trailing_3y", 50), row(name, "trailing_3y", 100), row(name, "full", 50)
            share, median, worst = rolling_win_share(paths[name][50], paths["aggressive_ceiling"][50])
            paired = paths[name][50].loc[r3.start:r3.end, "net_return"] - paths["aggressive_ceiling"][50].loc[r3.start:r3.end, "net_return"]
            raw_p = batch60.paired_block_pvalue(paired.to_numpy(), samples=int(config["bootstrap_samples"]), block=int(config["bootstrap_block_weeks"]), seed=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))
            adjusted = min(1.0, raw_p * int(config["multiple_testing_trials"]))
            rules = config["blend_gates"]
            checks = {
                "parent_source": source_pass[source],
                "three_year_return": r3.cagr - ceiling_rows["trailing_3y"].cagr >= rules["minimum_trailing_3y_cagr_improvement"],
                "one_year_guard": r1.cagr - ceiling_rows["trailing_1y"].cagr >= -rules["maximum_trailing_1y_cagr_sacrifice"],
                "two_year_guard": r2.cagr - ceiling_rows["trailing_2y"].cagr >= -rules["maximum_trailing_2y_cagr_sacrifice"],
                "cost_stress": r100.cagr - ceiling100.cagr >= rules["minimum_trailing_3y_100bps_improvement"],
                "recent_drawdown": abs(r3.max_drawdown) <= rules["maximum_recent_drawdown_magnitude"],
                "full_drawdown": abs(full.max_drawdown) <= rules["maximum_full_drawdown_magnitude"],
                "rolling_win_share": share >= rules["minimum_rolling_3y_win_share"],
                "adjusted_pvalue": adjusted <= rules["maximum_adjusted_pvalue"],
            }
            blend_rows.append({"candidate": name, "source": source, "source_weight": alpha, "trailing_1y_cagr": r1.cagr, "trailing_2y_cagr": r2.cagr, "trailing_3y_cagr": r3.cagr, "trailing_3y_cagr_vs_ceiling": r3.cagr - ceiling_rows["trailing_3y"].cagr, "trailing_3y_sharpe": r3.sharpe_zero_rf, "trailing_3y_100bps_cagr": r100.cagr, "recent_drawdown": r3.max_drawdown, "full_cagr": full.cagr, "full_drawdown": full.max_drawdown, "rolling_win_share": share, "rolling_median_cagr_difference": median, "rolling_worst_cagr_difference": worst, "raw_pvalue": raw_p, "adjusted_pvalue_64_trials": adjusted, **{f"gate_{key}": value for key, value in checks.items()}, "qualified": all(checks.values())})
    blends = pd.DataFrame(blend_rows).sort_values(["qualified", "trailing_3y_cagr"], ascending=False)
    passing = blends[blends.qualified]
    selected = str(passing.iloc[0].candidate) if len(passing) else None
    point_best = str(blends.iloc[0].candidate)
    saved = selected or point_best

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    standalone.to_csv(OUTPUT / "standalone_qualification.csv", index=False)
    blends.to_csv(OUTPUT / "blend_qualification.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    pd.DataFrame([{"source": name, "first_hash": batch60.frame_hash(frame), "second_hash": batch60.frame_hash(repeated[name]), "deterministic": batch60.frame_hash(frame) == batch60.frame_hash(repeated[name])} for name, frame in sources.items()]).to_csv(OUTPUT / "determinism.csv", index=False)
    saved_weights = candidates[saved].copy(); saved_weights.index.name = "Date"
    saved_weights.to_csv(OUTPUT / "selected_or_best_weights.csv")
    saved_weights.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_or_best_current_holdings.csv")
    best = blends.iloc[0]
    result = {
        "batch": 63, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "standalone_sources": expected_sources, "blend_trials": expected_blends,
        "qualified_standalone_sources": int(standalone.qualified.sum()), "qualified_blends": len(passing),
        "deterministic": deterministic, "prefix_invariance_pass": bool(prefixes.prefix_pass.all()),
        "maximum_prefix_weight_difference": float(prefixes.maximum_weight_difference.max()),
        "ceiling_trailing_3y_50bps_cagr": float(ceiling_rows["trailing_3y"].cagr),
        "best_point_blend": point_best, "best_point_trailing_1y_cagr": float(best.trailing_1y_cagr),
        "best_point_trailing_2y_cagr": float(best.trailing_2y_cagr), "best_point_trailing_3y_cagr": float(best.trailing_3y_cagr),
        "selected_blend": selected, "research_ceiling_blend": point_best,
        "decision": "save_independent_return_blend" if selected else "save_unqualified_independent_return_ceiling_for_confirmation",
        "retrospective_research_only": True, "leverage_used": False, "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Batch 63 — independent return-source discovery\n\n"
        f"Tested {expected_sources} causal standalone sources and {expected_blends} blends with the aggressive momentum ceiling. "
        f"Deterministic: **{deterministic}**. All {len(prefixes)} prefix checks passed: **{bool(prefixes.prefix_pass.all())}**.\n\n"
        f"Qualified standalone sources: **{int(standalone.qualified.sum())}**. Qualified blends: **{len(passing)}**. "
        f"Best point blend `{point_best}` produced one/two/three-year CAGR `{best.trailing_1y_cagr:.2%}` / `{best.trailing_2y_cagr:.2%}` / `{best.trailing_3y_cagr:.2%}` versus ceiling three-year CAGR `{ceiling_rows['trailing_3y'].cagr:.2%}`.\n\n"
        f"Selected blend: `{selected}`. Research ceiling retained even if unqualified: `{point_best}`. "
        f"Decision: `{result['decision']}`. No leverage, live trading, or forward clock was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if deterministic and bool(prefixes.prefix_pass.all()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
