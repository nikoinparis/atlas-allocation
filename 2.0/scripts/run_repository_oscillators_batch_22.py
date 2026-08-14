#!/usr/bin/env python3
"""Evaluate fixed MACD and Awesome Oscillator concepts with causal accounting."""

from __future__ import annotations

import csv
import json
import math
import os
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ml_confidence_overlay_batch_18 as batch18
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.oscillator_protocol import (
    adjusted_bar, capped_equal_weights, deterministic_matched_active,
    ewm_adjust_true, long_only_turnover, rolling_mean,
)
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/oscillator_program_v1.json"
OUTPUT = ROOT / "evidence/repository_oscillators_batch_22"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_22/source_rule_review.json"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
VARIANTS = (
    "macd_ewm_5_34", "awesome_zero_line", "awesome_source_saucer_overlay", "macd_sma_10_21",
    "awesome_inverted", "awesome_stale_1d", "awesome_stale_5d", "awesome_random_matched",
)
COSTS = (10.0, 50.0, 100.0)
PRIMARY_COST = 50.0


def enforce_deterministic_hash_seed() -> None:
    """Contain hash-order leakage in imported frozen portfolio reconstruction."""
    if os.environ.get("PYTHONHASHSEED") != "0":
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = "0"
        os.execve(sys.executable, [sys.executable, *sys.argv], environment)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: format(value, ".12g") if isinstance(value, float) else value for key, value in row.items()} for row in rows)


def load_bars(path: Path, assets: list[str], start: str) -> tuple[dict[str, list[dict[str, float | str]]], dict[str, object]]:
    selected: dict[str, list[dict[str, float | str]]] = {asset: [] for asset in assets}
    rejected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            asset, day = row["ticker"], row["observation_date"]
            if asset not in selected or day < start:
                continue
            try:
                bar = adjusted_bar(*(float(row[key]) for key in ("open", "high", "low", "close", "adjusted_close")))
            except (ValueError, TypeError):
                rejected += 1
                continue
            selected[asset].append({"date": day, **bar})
    for asset in assets:
        selected[asset].sort(key=lambda row: str(row["date"]))
        if len(selected[asset]) < 35:
            raise RuntimeError(f"insufficient adjusted OHLC for {asset}")
        if len({str(row['date']) for row in selected[asset]}) != len(selected[asset]):
            raise RuntimeError(f"duplicate dates for {asset}")
    return selected, {
        "assets": len(assets), "rows": sum(len(rows) for rows in selected.values()), "rejected_nonpositive_or_invalid": rejected,
        "first_date": min(str(rows[0]["date"]) for rows in selected.values()),
        "last_date": max(str(rows[-1]["date"]) for rows in selected.values()),
        "split_safe_adjustment": True,
    }


def build_signals(bars: dict[str, list[dict[str, float | str]]]) -> tuple[dict[str, dict[str, bool]], list[dict[str, object]]]:
    panels: dict[str, dict[str, bool]] = {name: {} for name in VARIANTS if name != "awesome_random_matched"}
    audit = []
    for asset, rows in bars.items():
        close = [float(row["close"]) for row in rows]
        median = [float(row["median"]) for row in rows]
        ewm5, ewm34 = ewm_adjust_true(close, 5), ewm_adjust_true(close, 34)
        sma_close10, sma_close21 = rolling_mean(close, 10), rolling_mean(close, 21)
        sma5, sma34 = rolling_mean(median, 5), rolling_mean(median, 34)
        primary: list[bool | None] = []
        for index, row in enumerate(rows):
            day = str(row["date"])
            if index < 33:
                primary.append(None)
                continue
            awesome = bool(float(sma5[index]) > float(sma34[index]))
            primary.append(awesome)
            panels["awesome_zero_line"][f"{day}|{asset}"] = awesome
            panels["macd_ewm_5_34"][f"{day}|{asset}"] = ewm5[index] >= ewm34[index]
            panels["macd_sma_10_21"][f"{day}|{asset}"] = float(sma_close10[index]) >= float(sma_close21[index])

            # The source's saucer assignments are overwritten. This diagnostic makes
            # those exact explicit transitions operative for one decision only.
            saucer = awesome
            bullish_source = (
                index >= 35 and float(row["close"]) < float(row["open"])
                and float(rows[index - 1]["close"]) > float(rows[index - 1]["open"])
                and float(rows[index - 2]["close"]) > float(rows[index - 2]["open"])
                and float(sma5[index - 1]) - float(sma34[index - 1]) > float(sma5[index - 2]) - float(sma34[index - 2])
                and float(sma5[index - 1]) - float(sma34[index - 1]) < 0.0
            )
            bearish_source = (
                index >= 35 and float(row["close"]) > float(row["open"])
                and float(rows[index - 1]["close"]) < float(rows[index - 1]["open"])
                and float(rows[index - 2]["close"]) < float(rows[index - 2]["open"])
                and float(sma5[index - 1]) - float(sma34[index - 1]) < float(sma5[index - 2]) - float(sma34[index - 2])
                and float(sma5[index - 1]) - float(sma34[index - 1]) > 0.0
            )
            if bullish_source:
                saucer = True
            elif bearish_source:
                saucer = False
            panels["awesome_source_saucer_overlay"][f"{day}|{asset}"] = saucer
            panels["awesome_inverted"][f"{day}|{asset}"] = not awesome
            for lag, name in ((1, "awesome_stale_1d"), (5, "awesome_stale_5d")):
                stale = primary[index - lag] if index >= lag else None
                if stale is not None:
                    panels[name][f"{day}|{asset}"] = bool(stale)
            audit.append({
                "decision_date": day, "asset": asset, "awesome": int(awesome),
                "macd": int(ewm5[index] >= ewm34[index]), "saucer_bullish": int(bullish_source),
                "saucer_bearish": int(bearish_source), "adjusted_close": close[index], "adjusted_median": median[index],
            })
    return panels, audit


def simulate_daily(
    variant: str, cost_bps: float, bars: dict[str, list[dict[str, float | str]]],
    panels: dict[str, dict[str, bool]], assets: list[str],
) -> list[dict[str, object]]:
    price = {f"{row['date']}|{asset}": float(row["close"]) for asset, rows in bars.items() for row in rows}
    all_dates = sorted({str(row["date"]) for rows in bars.values() for row in rows})
    previous = capped_equal_weights([], assets)
    periods = []
    for index in range(len(all_dates) - 1):
        decision, realization = all_dates[index], all_dates[index + 1]
        eligible = [asset for asset in assets if f"{decision}|{asset}" in panels["awesome_zero_line"] and f"{realization}|{asset}" in price]
        if not eligible:
            continue
        if variant == "awesome_random_matched":
            count = sum(bool(panels["awesome_zero_line"].get(f"{decision}|{asset}")) for asset in eligible)
            active = deterministic_matched_active(eligible, count, decision, 20260822)
        else:
            active = [asset for asset in eligible if panels[variant].get(f"{decision}|{asset}", False)]
        target = capped_equal_weights(active, assets)
        turnover = long_only_turnover(previous, target)
        asset_returns = {
            asset: price[f"{realization}|{asset}"] / price[f"{decision}|{asset}"] - 1.0
            for asset in eligible
        }
        gross = sum(target[asset] * asset_returns[asset] for asset in eligible)
        periods.append({
            "variant": variant, "decision_date": decision, "realization_date": realization,
            "cost_bps": cost_bps, "active_assets": len(active), "invested_weight": 1.0 - target["cash::USD"],
            "turnover": turnover, "gross_return": gross, "cost": turnover * cost_bps / 10_000.0,
            "net_return": gross - turnover * cost_bps / 10_000.0,
        })
        # The next trade begins from holdings after market drift, not the last
        # target. Costs are charged separately and do not create leverage.
        previous = {
            asset: target[asset] * (1.0 + asset_returns.get(asset, 0.0)) / (1.0 + gross)
            for asset in assets
        }
        previous["cash::USD"] = target["cash::USD"] / (1.0 + gross)
    return periods


def aggregate_weekly(daily: list[dict[str, object]], reference: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for week in reference:
        start, end = str(week["decision_date"]), str(week["realization_date"])
        selected = [row for row in daily if start < str(row["realization_date"]) <= end]
        if selected:
            result.append({
                "decision_date": start, "realization_date": end,
                "net_return": math.prod(1.0 + float(row["net_return"]) for row in selected) - 1.0,
                "turnover": sum(float(row["turnover"]) for row in selected),
                "mean_invested_weight": statistics.fmean(float(row["invested_weight"]) for row in selected),
                "daily_observations": len(selected),
            })
    return result


def metrics(rows: list[dict[str, object]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in selected]).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in selected) * 52.0
    result["mean_invested_weight"] = statistics.fmean(float(row["mean_invested_weight"]) for row in selected)
    return result


def paired_bootstrap_advantage(
    challenger: list[float], benchmark: list[float], *, seed: int,
    samples: int = 20_000, block_weeks: int = 13,
) -> dict[str, float | int | bool]:
    """Paired block bootstrap computing only the predeclared return/Sharpe tests."""
    if len(challenger) != len(benchmark) or not challenger:
        raise ValueError("paired bootstrap requires equal non-empty returns")
    generator = random.Random(seed)
    length = len(challenger)
    sharpe_differences = []
    return_differences = []
    for _ in range(samples):
        indexes = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(block_weeks))
        indexes = indexes[:length]
        left_sum = right_sum = left_square = right_square = left_log = right_log = 0.0
        for index in indexes:
            left, right = challenger[index], benchmark[index]
            left_sum += left
            right_sum += right
            left_square += left * left
            right_square += right * right
            left_log += math.log1p(left)
            right_log += math.log1p(right)
        left_deviation = math.sqrt(max(0.0, (left_square - left_sum * left_sum / length) / (length - 1)))
        right_deviation = math.sqrt(max(0.0, (right_square - right_sum * right_sum / length) / (length - 1)))
        left_sharpe = left_sum / length / left_deviation * math.sqrt(52.0) if left_deviation else 0.0
        right_sharpe = right_sum / length / right_deviation * math.sqrt(52.0) if right_deviation else 0.0
        sharpe_differences.append(left_sharpe - right_sharpe)
        return_differences.append(
            math.exp(left_log / length * 52.0) - math.exp(right_log / length * 52.0)
        )
    lower_index = math.floor(0.05 * (samples - 1))
    lower_sharpe = sorted(sharpe_differences)[lower_index]
    lower_return = sorted(return_differences)[lower_index]
    return {
        "observations": length, "samples": samples, "block_weeks": block_weeks,
        "mean_sharpe_difference": statistics.fmean(sharpe_differences),
        "one_sided_95pct_lower_sharpe_difference": lower_sharpe,
        "mean_annual_return_difference": statistics.fmean(return_differences),
        "one_sided_95pct_lower_annual_return_difference": lower_return,
        "sharpe_advantage_statistically_positive": lower_sharpe > 0.0,
        "annual_return_advantage_statistically_positive": lower_return > 0.0,
    }


def frozen_trend_periods(cost_bps: float) -> list[dict[str, object]]:
    source = ROOT / "evidence/strategy_rebuild_trend_quality/returns.csv"
    return [{
        "decision_date": row["decision_date"], "realization_date": row["realization_date"],
        "net_return": float(row["gross_return"]) - float(row["turnover"]) * cost_bps / 10_000.0,
    } for row in read_csv(source)]


def aligned_values(left: list[dict[str, object]], right: list[dict[str, object]]) -> tuple[list[float], list[float]]:
    right_map = {str(row["realization_date"]): float(row["net_return"]) for row in right}
    pairs = [(float(row["net_return"]), right_map[str(row["realization_date"])]) for row in left if str(row["realization_date"]) in right_map]
    return [item[0] for item in pairs], [item[1] for item in pairs]


def blend(core: list[dict[str, object]], oscillator: list[dict[str, object]], cost_bps: float) -> list[dict[str, object]]:
    oscillator_map = {str(row["realization_date"]): row for row in oscillator}
    rows = []
    first = True
    for row in core:
        day = str(row["realization_date"])
        if day not in oscillator_map:
            continue
        core_return = float(row["net_return"])
        oscillator_return = float(oscillator_map[day]["net_return"])
        gross = 0.8 * core_return + 0.2 * oscillator_return
        drifted = 0.2 * (1.0 + oscillator_return) / (1.0 + gross)
        turnover = 0.2 if first else abs(drifted - 0.2)
        first = False
        rows.append({
            "decision_date": row["decision_date"], "realization_date": day,
            "core_return": core_return, "oscillator_return": oscillator_return,
            "turnover": turnover, "mean_invested_weight": 1.0,
            "net_return": gross - turnover * cost_bps / 10_000.0,
        })
    return rows


def update_inventory() -> None:
    rows = read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "1":
            row.update(status="tested_batch_22_control", reason="Fixed EWM5/34 primary control and SMA10/21 diagnostic completed", next_action="Retain as benchmark evidence; not promoted")
        elif row["number"] == "5":
            row.update(status="tested_batch_22", reason="Zero-line rule and repaired source-saucer diagnostic completed with causal costs and controls", next_action="Follow Batch 22 promotion-gate decision")
        elif row["number"] == "2":
            row.update(status="tested_rejected_batch_21", reason="Independent causal implementation failed return cost stress and blend gates", next_action="Retain rejection evidence; do not promote")
    write_csv(INVENTORY, rows)


def main() -> int:
    enforce_deterministic_hash_seed()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot = str(program["data"]["snapshot_id"])
    assets = list(program["data"]["assets"])
    prices_path = ROOT / f"data/vintages/{snapshot}/payload/prices.csv"
    bars, data_audit = load_bars(prices_path, assets, str(program["data"]["start_date"]))
    panels, signal_audit = build_signals(bars)
    core_reference = batch18.frozen_winner_periods(PRIMARY_COST)
    weekly_tables: dict[tuple[str, float], list[dict[str, object]]] = {}
    scoreboard = []
    primary_daily = []
    for variant in VARIANTS:
        for cost in COSTS:
            daily = simulate_daily(variant, cost, bars, panels, assets)
            weekly = aggregate_weekly(daily, core_reference)
            weekly_tables[(variant, cost)] = weekly
            if variant == "awesome_zero_line" and cost == PRIMARY_COST:
                primary_daily = daily
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in metrics(weekly).items()},
                **{f"oos_2016_2020_{key}": value for key, value in metrics(weekly, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in metrics(weekly, "2021-01-01").items()},
            })
    awesome = next(row for row in scoreboard if row["variant"] == "awesome_zero_line" and row["cost_bps"] == PRIMARY_COST)
    macd = next(row for row in scoreboard if row["variant"] == "macd_ewm_5_34" and row["cost_bps"] == PRIMARY_COST)
    awesome_100 = next(row for row in scoreboard if row["variant"] == "awesome_zero_line" and row["cost_bps"] == 100.0)
    primary_weekly = weekly_tables[("awesome_zero_line", PRIMARY_COST)]
    macd_weekly = weekly_tables[("macd_ewm_5_34", PRIMARY_COST)]
    awesome_values, macd_values = aligned_values(primary_weekly, macd_weekly)
    paired_macd = paired_bootstrap_advantage(awesome_values, macd_values, seed=20260822)

    core = core_reference
    trend = frozen_trend_periods(PRIMARY_COST)
    awesome_core, core_values = aligned_values(primary_weekly, core)
    awesome_trend, trend_values = aligned_values(primary_weekly, trend)
    core_common_metrics = performance_metrics(core_values).to_dict()
    blend_rows = blend(core, primary_weekly, PRIMARY_COST)
    blend_values, blend_core = aligned_values(blend_rows, core)
    blend_metrics = performance_metrics(blend_values).to_dict()
    paired_blend = paired_bootstrap_advantage(blend_values, blend_core, seed=20260823)
    controls = [
        next(row for row in scoreboard if row["variant"] == name and row["cost_bps"] == PRIMARY_COST)
        for name in ("awesome_inverted", "awesome_stale_1d", "awesome_stale_5d", "awesome_random_matched")
    ]
    gates = {
        "beats_macd_point": (
            float(awesome["full_annual_return"]) > float(macd["full_annual_return"])
            and float(awesome["full_sharpe_zero_rf"]) > float(macd["full_sharpe_zero_rf"])
            and float(awesome["full_max_drawdown"]) >= float(macd["full_max_drawdown"])
        ),
        "beats_macd_paired_sharpe": bool(paired_macd["sharpe_advantage_statistically_positive"]),
        "stress_full_positive": float(awesome_100["full_annual_return"]) > 0.0,
        "stress_later_windows_positive": float(awesome_100["oos_2016_2020_annual_return"]) > 0.0 and float(awesome_100["oos_2021_present_annual_return"]) > 0.0,
        "negative_controls": float(awesome["full_sharpe_zero_rf"]) > max(float(row["full_sharpe_zero_rf"]) for row in controls),
        "dependence_core": abs(correlation(awesome_core, core_values)) <= 0.80,
        "dependence_trend": abs(correlation(awesome_trend, trend_values)) <= 0.80,
        "blend_point": float(blend_metrics["sharpe_zero_rf"]) > float(core_common_metrics["sharpe_zero_rf"]) and float(blend_metrics["max_drawdown"]) >= float(core_common_metrics["max_drawdown"]),
        "blend_paired_sharpe": bool(paired_blend["sharpe_advantage_statistically_positive"]),
        "survivorship_safe": False,
        "untouched_forward_52w": False,
    }
    gates["all"] = all(gates.values())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "primary_daily_returns_50bps.csv", primary_daily)
    write_csv(OUTPUT / "primary_weekly_returns_50bps.csv", primary_weekly)
    write_csv(OUTPUT / "blend_weekly_returns_50bps.csv", blend_rows)
    write_csv(OUTPUT / "signal_audit.csv", signal_audit)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 22,
        "track": "quant_trading_repository_macd_awesome", "program_sha256": sha256(PROGRAM),
        "source_rule_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "source_snapshot_manifest_sha256": sha256(ROOT / f"data/vintages/{snapshot}/manifest.json"),
        "data_audit": data_audit, "primary_awesome_50bps": awesome, "macd_control_50bps": macd,
        "awesome_stress_100bps": awesome_100, "paired_awesome_vs_macd": paired_macd,
        "correlation_to_frozen_core_50bps": correlation(awesome_core, core_values),
        "correlation_to_frozen_trend_v4_50bps": correlation(awesome_trend, trend_values),
        "common_core_metrics_50bps": core_common_metrics, "blend_metrics_50bps": blend_metrics,
        "paired_blend_advantage_50bps": paired_blend, "promotion_gates": gates,
        "promoted": gates["all"], "live_trading_approved": False,
        "limitations": [
            "The free current ETF list is survivorship-prone and not historical membership data.",
            "Adjusted OHLC is derived using the adjusted-close ratio and cannot recover intraday spreads or executable fills.",
            "The snapshot can contain vendor revisions made before acquisition.",
            "The repaired saucer is diagnostic because the source overwrites it and its stated conditions are ambiguous.",
            "All evidence is retrospective; no return is guaranteed and no live execution is approved."
        ],
    }
    (OUTPUT / "report.md").write_text("\n".join([
        "# Repository MACD vs Awesome Oscillator — Batch 22", "",
        f"At 50 bps, Awesome produced **{float(awesome['full_annual_return']) * 100:.2f}%** annual return, **{float(awesome['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(awesome['full_max_drawdown']) * 100:.2f}%** maximum drawdown.", "",
        f"The repository's EWM5/34 MACD control produced **{float(macd['full_annual_return']) * 100:.2f}%**, **{float(macd['full_sharpe_zero_rf']):.3f}**, and **{float(macd['full_max_drawdown']) * 100:.2f}%**, respectively. The paired Sharpe lower bound for Awesome minus MACD was **{float(paired_macd['one_sided_95pct_lower_sharpe_difference']):.3f}**.", "",
        f"At 100 bps Awesome returned **{float(awesome_100['full_annual_return']) * 100:.2f}%** annually. Correlations were **{result['correlation_to_frozen_trend_v4_50bps']:.3f}** to trend v4 and **{result['correlation_to_frozen_core_50bps']:.3f}** to the frozen core.", "",
        f"The 80/20 core-Awesome blend Sharpe was **{float(blend_metrics['sharpe_zero_rf']):.3f}** versus common-period core **{float(core_common_metrics['sharpe_zero_rf']):.3f}**. Promotion: **{gates['all']}**.", "",
        "The source's saucer branch is overwritten in its own loop. It was therefore retained only as an explicitly repaired diagnostic, never as a selection route.", "",
    ]), encoding="utf-8")
    result["artifacts"] = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in OUTPUT.iterdir()
        if path.is_file() and path.name not in {"result.json", "determinism_check.json"}
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps({"awesome_50bps": awesome, "macd_50bps": macd, "awesome_100bps": awesome_100, "correlations": {"core": result["correlation_to_frozen_core_50bps"], "trend": result["correlation_to_frozen_trend_v4_50bps"]}, "blend": blend_metrics, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
