"""B6 breadth decomposition diagnostics.

This research-only script separates breadth candidates into participation
confirmation, deterioration warning, risk-on expansion, defensive rotation, and
whipsaw/chop diagnostics. Natural and inverted signs are both tested for the
previously ambiguous diagnostics, but the output labels this explicitly to avoid
cherry-picking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    SIGNAL_DIR,
    ensure_parent,
    load_candidate_signal_panel,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
)
from run_b6_unified_signal_validation import HORIZONS, fast_ic_by_date, summarize_candidate


DECOMP_CANDIDATES = [
    ("bm_etf_above_50d_ma", "participation_confirmation", SIGNAL_DIR / "signal_bm_etf_above_50d_ma.csv", False),
    ("bm_etf_above_200d_ma", "participation_confirmation", SIGNAL_DIR / "signal_bm_etf_above_200d_ma.csv", False),
    ("bm_etf_positive_13w_mom", "participation_confirmation", SIGNAL_DIR / "signal_bm_etf_positive_13w_mom.csv", False),
    ("bm_etf_positive_26w_mom", "participation_confirmation", SIGNAL_DIR / "signal_bm_etf_positive_26w_mom.csv", False),
    ("bm_risk_on_participation", "risk_on_expansion", SIGNAL_DIR / "signal_bm_risk_on_participation.csv", False),
    ("bm_risk_on_minus_defensive_participation", "risk_on_expansion_vs_defensive_rotation", SIGNAL_DIR / "signal_bm_risk_on_minus_defensive_participation.csv", True),
    ("bm_offensive_vs_defensive_sector_breadth", "risk_on_expansion_vs_defensive_rotation", SIGNAL_DIR / "signal_bm_offensive_vs_defensive_sector_breadth.csv", True),
    ("bm_breadth_change_4w", "breadth_thrust", SIGNAL_DIR / "signal_bm_breadth_change_4w.csv", True),
    ("bm_breadth_momentum_13w", "breadth_thrust", SIGNAL_DIR / "signal_bm_breadth_momentum_13w.csv", True),
    ("bm_participation_acceleration", "whipsaw_chop_warning", SIGNAL_DIR / "signal_bm_participation_acceleration.csv", True),
    ("bm_quality_deterioration_warning", "deterioration_warning", SIGNAL_DIR / "signal_bm_quality_deterioration_warning.csv", True),
]


def classify_use(row: pd.Series, sign_variant: str) -> tuple[str, str]:
    holdout = row.get("2020_plus_avg_ic", np.nan)
    calm = row.get("calm_trend_avg_ic", np.nan)
    stress = row.get("stressed_panic_avg_ic", np.nan)
    full = row.get("avg_full_ic", np.nan)
    flags = str(row.get("stress_safety_flags", ""))
    if pd.notna(holdout) and holdout > 0.04 and pd.notna(stress) and stress > -0.02 and "redundancy_gt_0.60" not in flags:
        return "alpha_signal", "Positive holdout and acceptable stress behavior."
    if pd.notna(calm) and calm > 0.04 and pd.notna(stress) and stress > -0.03:
        return "offense_gate", "Strong calm_trend usefulness with tolerable stressed_panic behavior."
    if pd.notna(stress) and stress < -0.03 and sign_variant == "natural":
        return "risk_filter_or_invert_diagnostic", "Natural sign is dangerous in stressed_panic; inverted version should be inspected only as diagnostic."
    if pd.notna(full) and full < 0 and pd.notna(holdout) and holdout < 0:
        return "research_only_diagnostic", "Negative full and holdout IC; not a standalone alpha."
    if "2020_holdout_ic_negative" in flags or "2016_holdout_ic_negative" in flags:
        return "research_only_diagnostic", "Holdout instability prevents pass-through use."
    return "research_only_diagnostic", "Informative but not robust enough for alpha/pass-through."


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    existing = load_strong_existing_panels(warnings)
    rows: list[dict] = []
    state_rows: list[dict] = []
    selected_for_redundancy: dict[str, dict] = {}

    loaded: list[tuple[str, str, str, pd.DataFrame]] = []
    for name, role, path, test_inverted in DECOMP_CANDIDATES:
        if not path.exists():
            warnings.append(f"Missing breadth decomposition file: {path}")
            continue
        panel = load_candidate_signal_panel(path, warnings)
        if panel.empty:
            warnings.append(f"Empty breadth decomposition panel: {name}")
            continue
        panel = panel.copy()
        panel["signal_name"] = name
        loaded.append((name, role, "natural", panel[["Date", "Ticker", "signal_name", "signal_value_tradable"]]))
        if test_inverted:
            inv = panel.copy()
            inv["signal_name"] = f"{name}__inverted_diagnostic"
            inv["signal_value_tradable"] = -pd.to_numeric(inv["signal_value_tradable"], errors="coerce")
            loaded.append((f"{name}__inverted_diagnostic", role, "inverted_diagnostic", inv[["Date", "Ticker", "signal_name", "signal_value_tradable"]]))

    for name, role, sign_variant, panel in loaded:
        selected_for_redundancy[name] = {"panel": panel, "category": role, "gate": "none", "intended_use": "breadth_decomposition"}

    if not prices.empty:
        for name, role, sign_variant, panel in loaded:
            info = {"panel": panel, "category": role, "gate": "none", "intended_use": "breadth_decomposition"}
            row, state_part = summarize_candidate(name, info, prices, states, existing, selected_for_redundancy)
            row["breadth_component"] = role
            row["sign_variant"] = sign_variant
            suggested_use, reason = classify_use(pd.Series(row), sign_variant)
            row["suggested_use"] = suggested_use
            row["suggested_use_reason"] = reason
            rows.append(row)
            state_rows.extend(state_part)
    else:
        warnings.append("weekly_prices.csv unavailable; B6 breadth decomposition skipped.")

    result = pd.DataFrame(rows)
    out = SIGNAL_DIR / "b6_breadth_decomposition.csv"
    ensure_parent(out)
    result.to_csv(out, index=False)

    report_path = DOCS_RESEARCH_DIR / "b6_breadth_decomposition_report.md"
    report = [
        "# B6 Breadth Decomposition Report",
        "",
        "Research-only decomposition of breadth into participation confirmation, deterioration warning, risk-on expansion, defensive rotation, and whipsaw/chop diagnostics. Inverted signs are diagnostic only and are not optimization choices.",
        "",
        f"- Output CSV: `{out}`",
        f"- Rows tested: {len(result)}",
        "",
        "## Suggested Uses",
        "",
        markdown_table(
            result.sort_values(["suggested_use", "2020_plus_avg_ic"], ascending=[True, False])[
                [
                    "signal_name",
                    "breadth_component",
                    "sign_variant",
                    "suggested_use",
                    "avg_full_ic",
                    "2020_plus_avg_ic",
                    "2022_bear_rate_shock_avg_ic",
                    "calm_trend_avg_ic",
                    "stressed_panic_avg_ic",
                    "max_abs_redundancy_existing",
                    "suggested_use_reason",
                ]
            ],
            max_rows=30,
        )
        if not result.empty
        else "_No rows._",
        "",
        "## Diagnostic Sign Review",
        "",
        "- Participation confirmation breadth remains the cleanest breadth family.",
        "- Risk-on minus defensive breadth is informative, but the natural sign can behave poorly in stressed_panic and should be treated as a gate/filter candidate.",
        "- Deterioration warning signs remain diagnostic. Inverted signs are inspected only to understand orientation; they are not promoted.",
        "- Breadth thrust and acceleration are less stable than level/participation breadth.",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out} rows={len(result)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
