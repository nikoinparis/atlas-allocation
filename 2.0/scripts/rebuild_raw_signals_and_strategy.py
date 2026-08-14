#!/usr/bin/env python3
"""Re-derive five signals from weekly inputs and rebuild the strategy."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.point_in_time import read_wide_panel
from src.systematic_trader.raw_signals import reconstruct_five_signals

BASE_PATH = ROOT / "scripts/rebuild_trend_quality_strategy.py"
SPEC = importlib.util.spec_from_file_location("trend_quality_base", BASE_PATH)
base = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = base
SPEC.loader.exec_module(base)

OUTPUT = ROOT / "evidence/strategy_raw_formula_rebuild"
FILE_COLUMNS = {
    "signal_xsmom.csv": [
        "xsmom_raw_return_52_4w", "xsmom_raw_rank", "xsmom_score_observed", "xsmom_score_tradable",
    ],
    "signal_tsmom.csv": [
        "raw_tsmom_52_4w", "realized_vol_ann_26w", "tsmom_vol_scaled_observed",
        "tsmom_score_observed", "tsmom_vol_scaled_tradable", "tsmom_score_tradable",
    ],
    "signal_multi_horizon_mom.csv": [
        "mom_13_4w", "mom_26_4w", "mom_39_4w", "mom_52_4w",
        "multi_mom_equal_observed", "multi_mom_equal_score_observed", "multi_mom_equal_score_tradable",
        "multi_mom_invvol_observed", "multi_mom_invvol_score_observed", "multi_mom_invvol_score_tradable",
    ],
    "signal_trend_quality.csv": [
        "trend_clarity_r2_observed", "trend_clarity_momentum_raw_observed",
        "trend_clarity_momentum_raw_tradable", "trend_clarity_momentum_score_observed",
        "trend_clarity_momentum_score_tradable",
    ],
    "signal_moving_average_distance.csv": [
        "ma_13w_observed", "ma_52w_observed", "moving_average_distance_observed",
        "moving_average_distance_tradable", "moving_average_distance_score_observed",
        "moving_average_distance_score_tradable",
    ],
}


def optional(value: str | None) -> float | None:
    return None if value in (None, "") else float(value)


def compare_component(panel, saved: dict[tuple[str, str], dict[str, str]], column: str, dates: list[str], assets: list[str]) -> dict[str, int | float | bool]:
    comparisons = 0
    mismatches = 0
    missingness = 0
    max_error = 0.0
    for day in dates:
        for asset in assets:
            expected = optional(saved[(day, asset)].get(column))
            actual = panel[day][asset]
            if expected is None or actual is None:
                missingness += (expected is None) != (actual is None)
                continue
            comparisons += 1
            error = abs(expected - actual)
            max_error = max(max_error, error)
            mismatches += error > 1e-10
    return {
        "numeric_comparisons": comparisons,
        "numeric_mismatches_over_1e_10": mismatches,
        "missingness_mismatches": missingness,
        "max_absolute_error": max_error,
        "reconstruction_pass": mismatches == 0 and missingness == 0,
    }


def build() -> dict[str, object]:
    dates, assets, prices = read_wide_panel(base.DATA_HUB / "weekly_prices.csv")
    _, _, return_rows = read_wide_panel(base.DATA_HUB / "weekly_returns.csv")
    aligned_log_returns = {day: {asset: return_rows.get(day, {}).get(asset) for asset in assets} for day in dates}
    strategy_panels, components = reconstruct_five_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=aligned_log_returns
    )

    component_audits: dict[str, dict[str, int | float | bool]] = {}
    for file_name, columns in FILE_COLUMNS.items():
        with (base.SIGNAL_DIR / file_name).open(encoding="utf-8", newline="") as handle:
            saved = {(row["Date"], row["Ticker"]): row for row in csv.DictReader(handle)}
        for column in columns:
            component_audits[column] = compare_component(components[column], saved, column, dates, assets)

    formula_pass = all(bool(audit["reconstruction_pass"]) for audit in component_audits.values())
    result = base.build(precomputed_panels=strategy_panels)
    result["strategy"] = "composite_trend_quality_refined_raw_rebuilt_v3"
    result["evidence_grade"] = "B-raw-rebuilt" if formula_pass else "C-raw-rebuild-mismatch"
    result["raw_formula_audit"] = {
        "input_frequency": "weekly",
        "input_price_assets": len(assets),
        "input_weeks": len(dates),
        "component_columns_checked": len(component_audits),
        "all_formula_components_reconstruct": formula_pass,
        "total_numeric_comparisons": sum(int(item["numeric_comparisons"]) for item in component_audits.values()),
        "total_numeric_mismatches_over_1e_10": sum(int(item["numeric_mismatches_over_1e_10"]) for item in component_audits.values()),
        "total_missingness_mismatches": sum(int(item["missingness_mismatches"]) for item in component_audits.values()),
        "maximum_component_absolute_error": max(float(item["max_absolute_error"]) for item in component_audits.values()),
        "components": component_audits,
    }
    result["limitations"][0] = (
        "All five weekly signal formulas and their intermediate columns were independently re-derived from weekly prices and returns."
        if formula_pass else
        "The raw signal reconstruction differs from one or more saved intermediate columns; see raw_formula_audit."
    )
    return result


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def report(result: dict[str, object]) -> str:
    raw = result["raw_formula_audit"]
    audit = result["audit"]
    metrics = result["metrics"]
    rebuilt = metrics["rebuilt"]["full_10bps"]
    recent = metrics["rebuilt"]["recent_since_2021_10bps"]
    bootstrap = metrics["rebuilt"]["block_bootstrap_95pct"]
    rolling = metrics["rebuilt"]["rolling_3y"]
    stress = metrics["cost_stress"]
    return "\n".join([
        "# Raw-Formula Point-in-Time Rebuild", "",
        "All five strategy signals were recalculated in platform-owned code from weekly prices and weekly log returns. The saved strategy returns and saved signal values were not used to generate the new portfolio.", "",
        "## Formula audit", "",
        f"- Intermediate columns checked: **{raw['component_columns_checked']}**.",
        f"- Numeric comparisons: **{raw['total_numeric_comparisons']:,}**.",
        f"- Numeric mismatches above 1e-10: **{raw['total_numeric_mismatches_over_1e_10']}**.",
        f"- Missingness mismatches: **{raw['total_missingness_mismatches']}**.",
        f"- Maximum absolute numerical error: **{float(raw['maximum_component_absolute_error']):.3e}**.",
        f"- Complete formula reconstruction passed: **{'yes' if raw['all_formula_components_reconstruct'] else 'no'}**.", "",
        "## Portfolio audit", "",
        f"- Unpriced nonzero exposures: **{audit['unpriced_exposure_events']}**.",
        f"- Fully invested and cost reconciliation passed: **{'yes' if audit['fully_invested_pass'] and audit['cost_identity_pass'] else 'no'}**.",
        f"- Current inputs reproduce old saved positions: **{'yes' if audit['current_signal_inputs_reproduce_saved_positions'] else 'no'}**; the old artifact remains comparison-only.",
        f"- Evidence label: **{result['evidence_grade']}, research only**.", "",
        "## Candidate-of-record performance", "",
        f"- Annual return: **{pct(rebuilt['annual_return'])}**.",
        f"- Sharpe (0% risk-free rate): **{float(rebuilt['sharpe_zero_rf']):.3f}**.",
        f"- Maximum drawdown: **{pct(rebuilt['max_drawdown'])}**.",
        f"- Since-2021 annual return / Sharpe: **{pct(recent['annual_return'])} / {float(recent['sharpe_zero_rf']):.3f}**.",
        f"- 50 bps turnover stress return / Sharpe: **{pct(stress['50bps']['annual_return'])} / {float(stress['50bps']['sharpe_zero_rf']):.3f}**.",
        f"- Bootstrap 95% annual-return range: **{pct(bootstrap['annual_return_ci_low'])} to {pct(bootstrap['annual_return_ci_high'])}**.",
        f"- Bootstrap 95% Sharpe range: **{float(bootstrap['sharpe_ci_low']):.3f} to {float(bootstrap['sharpe_ci_high']):.3f}**.",
        f"- Rolling three-year SPY win share: **{pct(rolling['spy_win_3y_share'])}**.", "",
        "## Remaining limits", "",
        "This is a weekly-data reconstruction, not a vintage-by-vintage vendor-data replay. The universe and strategy were selected using already-seen history, and the data can still contain survivorship or later-revision effects. Promotion remains blocked until the locked forward record has at least 52 untouched weeks.", "",
    ])


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    result = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    weights = result.pop("weights")
    periods = result.pop("periods")
    write_csv(OUTPUT / "positions.csv", [{"Date": day, **row} for day, row in weights.items()])
    write_csv(OUTPUT / "returns.csv", periods)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({"raw_formula_audit": result["raw_formula_audit"], "metrics": result["metrics"]["rebuilt"]["full_10bps"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
