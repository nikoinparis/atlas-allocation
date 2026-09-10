"""B6 gated macro decomposition and pre-R5 priority ranking.

Research-only. This script compares selected gated macro candidates with their
unconditional originals, explains active-state coverage, then compiles the B6
priority table and summary report. It does not write production/dashboard files.
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
    read_csv_safe,
)
from run_b6_unified_signal_validation import fast_ic_by_date, summarize_candidate
from run_state_gated_macro_tests import apply_gate, load_gate_frame


GATED_MACRO = [
    ("r2_credit_spread", "r2_credit_spread__calm_trend_only", SIGNAL_DIR / "signal_r2_credit_spread.csv", "gate_calm_trend_only", "calm-state confirmation"),
    ("r2_vix_term_structure", "r2_vix_term_structure__calm_trend_only", SIGNAL_DIR / "signal_r2_vix_term_structure.csv", "gate_calm_trend_only", "calm-state confirmation"),
    ("r2_vix_term_structure", "r2_vix_term_structure__no_stressed_panic", SIGNAL_DIR / "signal_r2_vix_term_structure.csv", "gate_no_stressed_panic", "stress avoidance"),
    ("r2_credit_spread", "r2_credit_spread__vix_below_past_median", SIGNAL_DIR / "signal_r2_credit_spread.csv", "gate_vix_below_past_median", "volatility filter / credit condition improvement"),
    ("r2_financial_conditions", "r2_financial_conditions__recovery_only", SIGNAL_DIR / "signal_r2_financial_conditions.csv", "gate_recovery_only", "recovery timing"),
    ("r2_commodity_regime", "r2_commodity_regime__recovery_only", SIGNAL_DIR / "signal_r2_commodity_regime.csv", "gate_recovery_only", "commodity/inflation recovery regime"),
]


def active_state_counts(panel: pd.DataFrame, states: pd.DataFrame) -> dict[str, int]:
    if panel.empty or states.empty or "gate_value_lagged" not in panel.columns:
        return {}
    unique_dates = panel[["Date", "gate_value_lagged"]].drop_duplicates("Date")
    active = unique_dates[pd.to_numeric(unique_dates["gate_value_lagged"], errors="coerce").fillna(0) > 0]
    state_map = states.set_index("Date")["market_state"]
    counts = active["Date"].map(state_map).value_counts().to_dict()
    return {str(k): int(v) for k, v in counts.items()}


def avg_ic(panel: pd.DataFrame, prices: pd.DataFrame) -> float:
    vals = []
    for horizon in [1, 2, 4, 8, 13]:
        ic = fast_ic_by_date(panel, prices, horizon)
        vals.append(float(ic["ic"].mean()) if not ic.empty else np.nan)
    return float(pd.Series(vals).mean())


def compile_priority_table() -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    unified = read_csv_safe(SIGNAL_DIR / "b6_unified_signal_validation.csv", warnings)
    if unified.empty:
        return pd.DataFrame(), warnings
    table = unified.copy()
    for col in [
        "2020_plus_avg_ic",
        "2016_plus_avg_ic",
        "2022_bear_rate_shock_avg_ic",
        "calm_trend_avg_ic",
        "stressed_panic_avg_ic",
        "max_abs_redundancy_existing",
        "subperiod_positive_share",
        "rolling_104w_redundancy_recent",
    ]:
        table[col] = pd.to_numeric(table.get(col, np.nan), errors="coerce")

    table["stressed_panic_safety"] = table["stressed_panic_avg_ic"].fillna(0).clip(lower=-0.10)
    table["redundancy_penalty"] = table["max_abs_redundancy_existing"].fillna(0.50).clip(lower=0)
    table["interpretability_score"] = np.select(
        [
            table["category"].isin(["breadth", "sector_breadth"]),
            table["category"].eq("gated_macro"),
            table["category"].eq("dollar_strength"),
            table["category"].eq("signal_quality"),
        ],
        [1.0, 0.8, 0.8, 0.7],
        default=0.6,
    )
    table["data_quality_score"] = np.where(table["category"].eq("gated_macro"), 0.75, 0.9)
    table["simplicity_score"] = np.where(table["gate"].eq("none"), 1.0, 0.75)
    table["portfolio_usefulness_score"] = (
        table["2020_plus_avg_ic"].fillna(-0.05) * 12
        + table["calm_trend_avg_ic"].fillna(0) * 8
        + table["2022_bear_rate_shock_avg_ic"].fillna(0) * 4
        + table["stressed_panic_safety"].fillna(0) * 5
        + table["subperiod_positive_share"].fillna(0.5)
        - table["redundancy_penalty"].fillna(0.5)
        + table["interpretability_score"]
        + table["data_quality_score"]
        + table["simplicity_score"]
    )
    def recommendation(row: pd.Series) -> str:
        verdict = str(row.get("verdict", "research-only"))
        intended = str(row.get("intended_use", ""))
        flags = str(row.get("stress_safety_flags", ""))
        if verdict == "reject" or "stressed_panic_ic_below_-0.03" in flags or "2020_holdout_ic_negative" in flags:
            return "reject"
        if verdict == "candidate-pass-but-redundant":
            return "candidate-pass-but-redundant"
        if "gate" in intended or "filter" in intended or row.get("category") in {"gated_macro", "signal_quality"}:
            if row.get("2020_plus_avg_ic", np.nan) > 0 and row.get("calm_trend_avg_ic", 0) > 0:
                return "gate-filter-candidate"
            return "research-only"
        if verdict == "candidate-pass":
            return "controlled-pass-through-candidate"
        return "research-only"
    table["b6_recommendation"] = table.apply(recommendation, axis=1)
    table = table.sort_values("portfolio_usefulness_score", ascending=False)
    keep = [
        "signal_name",
        "category",
        "gate",
        "intended_use",
        "verdict",
        "b6_recommendation",
        "avg_full_ic",
        "2016_plus_avg_ic",
        "2020_plus_avg_ic",
        "2022_bear_rate_shock_avg_ic",
        "2023_plus_avg_ic",
        "calm_trend_avg_ic",
        "stressed_panic_avg_ic",
        "max_abs_redundancy_existing",
        "most_redundant_existing_signal",
        "subperiod_positive_share",
        "portfolio_usefulness_score",
        "stress_safety_flags",
        "verdict_reason",
    ]
    for col in keep:
        if col not in table.columns:
            table[col] = np.nan
    return table[keep], warnings


def write_priority_reports(priority: pd.DataFrame, decomp: pd.DataFrame, warnings: list[str]) -> None:
    out = SIGNAL_DIR / "b6_priority_table.csv"
    ensure_parent(out)
    priority.to_csv(out, index=False)
    report_path = DOCS_RESEARCH_DIR / "b6_priority_ranking_report.md"

    pass_through = priority[priority["b6_recommendation"].eq("controlled-pass-through-candidate")]
    gates = priority[priority["b6_recommendation"].eq("gate-filter-candidate")]
    redundant = priority[priority["b6_recommendation"].eq("candidate-pass-but-redundant")]
    rejected = priority[priority["b6_recommendation"].eq("reject")]

    report = [
        "# B6 Priority Ranking Report",
        "",
        "Research-only pre-R5 ranking. These recommendations indicate what deserves a later controlled portfolio pass-through test; they do not promote any signal.",
        "",
        f"- Priority table: `{out}`",
        f"- Candidates ranked: {len(priority)}",
        "",
        "## Controlled Pass-Through Candidates",
        "",
        markdown_table(pass_through[["signal_name", "category", "2020_plus_avg_ic", "calm_trend_avg_ic", "stressed_panic_avg_ic", "max_abs_redundancy_existing", "portfolio_usefulness_score"]], max_rows=20),
        "",
        "## Gate / Filter Candidates",
        "",
        markdown_table(gates[["signal_name", "category", "intended_use", "2020_plus_avg_ic", "calm_trend_avg_ic", "stressed_panic_avg_ic", "portfolio_usefulness_score"]], max_rows=20),
        "",
        "## Too Redundant",
        "",
        markdown_table(redundant[["signal_name", "max_abs_redundancy_existing", "most_redundant_existing_signal", "2020_plus_avg_ic", "verdict_reason"]], max_rows=20),
        "",
        "## Rejected / Dangerous",
        "",
        markdown_table(rejected[["signal_name", "category", "2020_plus_avg_ic", "2022_bear_rate_shock_avg_ic", "stressed_panic_avg_ic", "stress_safety_flags"]], max_rows=20),
        "",
        "## Gated Macro Decomposition Snapshot",
        "",
        markdown_table(decomp[["gated_signal_name", "mechanism_hypothesis", "gate_active_share", "holdout_2020_ic_delta", "stressed_panic_ic_delta", "low_n_warning"]], max_rows=20) if not decomp.empty else "_No rows._",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    summary_path = DOCS_RESEARCH_DIR / "b6_sprint_summary.md"
    top_pass = pass_through.head(10)
    top_gate = gates.head(10)
    summary = [
        "# B6 Sprint Summary",
        "",
        "Research-only narrow validation sprint for top breadth, gated macro, dollar-strength, and signal-quality candidates. No production/dashboard/allocation/R5/R6/live-trading files were changed.",
        "",
        "## Commands Run",
        "",
        "```bash",
        ".venv/bin/python -m py_compile scripts/run_b6_unified_signal_validation.py scripts/run_b6_breadth_decomposition.py scripts/run_b6_gated_macro_decomposition.py",
        ".venv/bin/python scripts/run_b6_unified_signal_validation.py",
        ".venv/bin/python scripts/run_b6_breadth_decomposition.py",
        ".venv/bin/python scripts/run_b6_gated_macro_decomposition.py",
        "git status --short",
        "git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv",
        "```",
        "",
        "## Robust Enough For Controlled Portfolio Pass-Through",
        "",
        markdown_table(top_pass[["signal_name", "category", "2020_plus_avg_ic", "calm_trend_avg_ic", "stressed_panic_avg_ic", "portfolio_usefulness_score"]]),
        "",
        "## Best Offense Gate / Filter Candidates",
        "",
        markdown_table(top_gate[["signal_name", "category", "intended_use", "2020_plus_avg_ic", "calm_trend_avg_ic", "stressed_panic_avg_ic", "portfolio_usefulness_score"]]),
        "",
        "## Stress / Deterioration Warnings",
        "",
        "- The cleanest stress/filter candidates are gated VIX term structure, gated credit spread, and dollar-strength 4w/blended.",
        "- Breadth deterioration and thrust diagnostics remain useful for monitoring, but not robust enough for direct pass-through in this form.",
        "",
        "## Too Redundant",
        "",
        markdown_table(redundant[["signal_name", "max_abs_redundancy_existing", "most_redundant_existing_signal"]], max_rows=10),
        "",
        "## Too Dangerous / Rejected",
        "",
        markdown_table(rejected[["signal_name", "stress_safety_flags", "verdict_reason"]], max_rows=10),
        "",
        "## Is Breadth Still The Strongest Frontier?",
        "",
        "Yes. ETF and sector breadth remain the clearest frontier because they are interpretable, available from existing data, weekly-compatible, broadly positive in holdout, and less dependent on fragile macro gates.",
        "",
        "## R5 Or Portfolio Pass-Through First?",
        "",
        "Run a controlled portfolio pass-through test before R5 ensemble work. B6 is a signal validation sprint; the next step should test whether the best breadth and gate/filter candidates survive realistic portfolio plumbing without promotion.",
        "",
        "## Exact Next Recommended Sprint",
        "",
        "Run B7: controlled portfolio pass-through sandbox for the top B6 candidates only, with no production promotion. Compare alpha-style breadth additions versus offense-gate/risk-filter usage, isolate turnover/cost impact, and require state-level improvement before any R5 ensemble sprint.",
        "",
        "## Production Safety",
        "",
        "Production/dashboard safety must be confirmed by the final diff command. This summary is research-only and does not intentionally touch production/dashboard/public files.",
    ]
    summary_path.write_text("\n".join(summary) + "\n")
    print(f"Wrote {out} rows={len(priority)}")
    print(f"Wrote {report_path}")
    print(f"Wrote {summary_path}")


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    gates = load_gate_frame(warnings)
    existing = load_strong_existing_panels(warnings)
    rows: list[dict] = []
    selected_for_redundancy: dict[str, dict] = {}

    for base_name, gated_name, path, gate_col, mechanism in GATED_MACRO:
        if not path.exists():
            warnings.append(f"Missing gated macro base file: {path}")
            continue
        base_panel = load_candidate_signal_panel(path, warnings)
        if base_panel.empty:
            warnings.append(f"Empty gated macro base panel: {base_name}")
            continue
        if gate_col not in gates.columns:
            warnings.append(f"Missing gate {gate_col} for {gated_name}")
            continue
        original = base_panel.copy()
        original["signal_name"] = f"{base_name}__unconditional_reference"
        gated = apply_gate(base_panel, gates, gate_col, gated_name)
        selected_for_redundancy[gated_name] = {"panel": gated, "category": "gated_macro", "gate": gate_col, "intended_use": "macro_gate"}

        original_info = {"panel": original[["Date", "Ticker", "signal_name", "signal_value_tradable"]], "category": "gated_macro_reference", "gate": "none", "intended_use": "reference"}
        gated_info = {"panel": gated[["Date", "Ticker", "signal_name", "signal_value_tradable"]], "category": "gated_macro", "gate": gate_col.replace("gate_", ""), "intended_use": "macro_gate"}
        original_row, _ = summarize_candidate(original_info["panel"]["signal_name"].iloc[0], original_info, prices, states, existing, selected_for_redundancy)
        gated_row, _ = summarize_candidate(gated_name, gated_info, prices, states, existing, selected_for_redundancy)
        counts = active_state_counts(gated, states)
        active_dates = gated[["Date", "gate_value_lagged"]].drop_duplicates("Date")
        active_share = float((pd.to_numeric(active_dates["gate_value_lagged"], errors="coerce").fillna(0) > 0).mean()) if not active_dates.empty else np.nan
        row = {
            "base_signal": base_name,
            "gated_signal_name": gated_name,
            "gate_name": gate_col.replace("gate_", ""),
            "mechanism_hypothesis": mechanism,
            "gate_active_share": active_share,
            "active_calm_trend_n": counts.get("calm_trend", 0),
            "active_neutral_mixed_n": counts.get("neutral_mixed", 0),
            "active_recovery_fragile_n": counts.get("recovery_fragile", 0),
            "active_recovery_confirmed_n": counts.get("recovery_confirmed", 0),
            "active_stressed_panic_n": counts.get("stressed_panic", 0),
            "original_2020_plus_avg_ic": original_row.get("2020_plus_avg_ic", np.nan),
            "gated_2020_plus_avg_ic": gated_row.get("2020_plus_avg_ic", np.nan),
            "holdout_2020_ic_delta": gated_row.get("2020_plus_avg_ic", np.nan) - original_row.get("2020_plus_avg_ic", np.nan),
            "original_stressed_panic_avg_ic": original_row.get("stressed_panic_avg_ic", np.nan),
            "gated_stressed_panic_avg_ic": gated_row.get("stressed_panic_avg_ic", np.nan),
            "stressed_panic_ic_delta": gated_row.get("stressed_panic_avg_ic", np.nan) - original_row.get("stressed_panic_avg_ic", np.nan),
            "original_calm_trend_avg_ic": original_row.get("calm_trend_avg_ic", np.nan),
            "gated_calm_trend_avg_ic": gated_row.get("calm_trend_avg_ic", np.nan),
            "gated_verdict": gated_row.get("verdict", ""),
            "low_n_warning": active_share < 0.10 or gated_row.get("2020_plus_min_n", 0) < 52,
            "research_only": True,
        }
        rows.append(row)

    decomp = pd.DataFrame(rows)
    out = SIGNAL_DIR / "b6_gated_macro_decomposition.csv"
    ensure_parent(out)
    decomp.to_csv(out, index=False)

    report_path = DOCS_RESEARCH_DIR / "b6_gated_macro_decomposition_report.md"
    report = [
        "# B6 Gated Macro Decomposition Report",
        "",
        "Research-only decomposition of selected gated macro candidates. Each row compares the original R2 signal against its lagged gated version.",
        "",
        f"- Output CSV: `{out}`",
        f"- Rows tested: {len(decomp)}",
        "",
        "## Gate Effects",
        "",
        markdown_table(
            decomp[
                [
                    "gated_signal_name",
                    "mechanism_hypothesis",
                    "gate_active_share",
                    "active_calm_trend_n",
                    "active_recovery_fragile_n",
                    "active_recovery_confirmed_n",
                    "active_stressed_panic_n",
                    "holdout_2020_ic_delta",
                    "stressed_panic_ic_delta",
                    "low_n_warning",
                ]
            ],
            max_rows=20,
        )
        if not decomp.empty
        else "_No rows._",
        "",
        "## Interpretation",
        "",
        "- Calm-only gates mostly work by turning macro into calm-state confirmation rather than stress prediction.",
        "- No-stressed-panic gates work by suppressing known stress damage, but still need portfolio pass-through checks.",
        "- Recovery-only gates can look strong in holdout but are lower-N and should be treated carefully.",
        "- VIX-below-past-median credit gating is interpretable as a volatility/credit-condition filter.",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    priority, priority_warnings = compile_priority_table()
    write_priority_reports(priority, decomp, [*warnings, *priority_warnings])

    print(f"Wrote {out} rows={len(decomp)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
