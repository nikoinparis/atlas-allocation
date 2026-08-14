"""C3 confidence inputs for allocator-native insertion research.

Research-only. Builds normalized weekly confidence inputs aligned exactly to
the saved GGG weekly index. Inputs come from existing tradable signal files and
market-state history; no paid data, production pins, dashboard files, or Layer 3
production artifacts are modified.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    PHASE2B,
    PORT,
    PRODUCTION_COST_BPS,
    WEEKS,
    DEFENSE,
    OFFENSE,
    ensure_dirs,
    exposure_summary,
    load_market_quality_inputs,
    load_next_week_returns,
    load_production_summary,
    load_returns,
    load_states,
    load_weights,
    md_table,
    metrics_from_path,
    production_portfolio_path,
    read_csv,
    rel,
    write_text,
)


NATIVE_OUT = Path("data") / "research" / "native_confidence"


def lagged(s: pd.Series) -> pd.Series:
    """Use one additional week of conservatism for newly composed scores."""
    return pd.Series(s, dtype=float).shift(1).ffill().fillna(0.5).clip(0.0, 1.0)


def build_scores(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    raw = load_market_quality_inputs(index, warnings)
    out = pd.DataFrame(index=index)

    etf_cols = ["bm_etf_above_50d_ma", "bm_etf_above_200d_ma", "bm_etf_positive_13w_mom", "bm_etf_positive_26w_mom"]
    sector_cols = ["bm_sector_above_50d_ma", "bm_sector_above_200d_ma", "bm_sector_positive_13w_mom", "bm_sector_positive_26w_mom"]

    out["breadth_confidence"] = lagged(raw[etf_cols].mean(axis=1))
    out["sector_confidence"] = lagged(raw[sector_cols].mean(axis=1))
    out["risk_on_confidence"] = lagged(raw["bm_risk_on_participation"])
    # Higher filter score means macro stress is low / confidence is usable.
    out["macro_stress_filter"] = lagged(
        1.0 - (
            0.40 * (1.0 - raw["r2_vix_term_structure"])
            + 0.40 * (1.0 - raw["r2_credit_spread"])
            + 0.20 * (1.0 - raw["r2_financial_conditions"])
        ).clip(0.0, 1.0)
    )
    # Higher filter score means dollar pressure is low.
    out["dollar_pressure_filter"] = lagged(1.0 - (0.55 * raw["bm_dollar_strength_blended"] + 0.45 * raw["bm_dollar_strength_4w"]))

    transition_raw = pd.to_numeric(raw.get("transition_non_stress_prob", pd.Series(index=index)), errors="coerce")
    transition_raw = transition_raw.fillna(transition_raw.expanding(min_periods=20).median()).fillna(0.5).clip(0.0, 1.0)
    out["transition_quality_score"] = lagged(
        0.45 * transition_raw
        + 0.20 * out["breadth_confidence"]
        + 0.15 * out["sector_confidence"]
        + 0.10 * out["risk_on_confidence"]
        + 0.10 * out["macro_stress_filter"]
    )

    signal_agreement = raw.get("bm_quality_signal_agreement", pd.Series(0.5, index=index)).astype(float)
    signal_dispersion = raw.get("bm_quality_signal_dispersion", pd.Series(0.5, index=index)).astype(float)
    out["signal_agreement"] = lagged(signal_agreement)
    out["signal_dispersion"] = lagged(signal_dispersion)
    out["offense_eligibility_score"] = lagged(
        0.25 * out["breadth_confidence"]
        + 0.20 * out["sector_confidence"]
        + 0.20 * out["risk_on_confidence"]
        + 0.15 * out["transition_quality_score"]
        + 0.10 * out["macro_stress_filter"]
        + 0.10 * out["dollar_pressure_filter"]
    )
    out["deterioration_score"] = (
        1.0
        - (
            0.25 * out["breadth_confidence"]
            + 0.20 * out["sector_confidence"]
            + 0.15 * out["risk_on_confidence"]
            + 0.15 * out["macro_stress_filter"]
            + 0.15 * out["dollar_pressure_filter"]
            + 0.10 * (1.0 - out["signal_dispersion"])
        )
    ).clip(0.0, 1.0)
    out["combined_market_quality_score"] = lagged(
        0.24 * out["breadth_confidence"]
        + 0.18 * out["sector_confidence"]
        + 0.16 * out["risk_on_confidence"]
        + 0.16 * out["transition_quality_score"]
        + 0.12 * out["macro_stress_filter"]
        + 0.08 * out["dollar_pressure_filter"]
        + 0.06 * out["signal_agreement"]
    )

    for col in ["market_state", "risk_state"]:
        if col in raw.columns:
            out[col] = raw[col].reindex(index).ffill()

    out["macro_stress_active"] = out["macro_stress_filter"] < 0.40
    out["dollar_pressure_active"] = out["dollar_pressure_filter"] < 0.35
    out["offense_eligible"] = (
        (out["offense_eligibility_score"] >= 0.55)
        & (out["deterioration_score"] <= 0.62)
        & (~out["macro_stress_active"])
    )
    out["research_only"] = True
    return out.reset_index().rename(columns={"index": "Date"})


def write_c1_baseline_note(warnings: list[str]) -> None:
    rebuild = read_csv(NATIVE_OUT.parent / "path1_rebuild" / "ggg_rebuild_metrics.csv", warnings)
    returns = load_returns(GGG, warnings)
    weights = load_weights(GGG, warnings)
    states = load_states(warnings)
    next_returns = load_next_week_returns(warnings)
    exact_path = production_portfolio_path(weights, next_returns, PRODUCTION_COST_BPS) if not weights.empty and not next_returns.empty else pd.DataFrame()
    exact_metrics = metrics_from_path(exact_path) if not exact_path.empty else {}
    exact_row = rebuild[rebuild.get("rebuild_name", pd.Series(dtype=str)).eq("exact_saved_final_etf_weights")] if not rebuild.empty else pd.DataFrame()
    state_counts = states["market_state"].value_counts().reset_index() if not states.empty else pd.DataFrame()
    if not state_counts.empty:
        state_counts.columns = ["market_state", "n_weeks"]

    lines = [
        "# C1 Exact GGG Baseline Note",
        "",
        "Research-only baseline confirmation for allocator-native confidence insertion.",
        "",
        "## Exact Reconstruction Evidence",
        "",
        md_table(exact_row, ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "rebuild_max_drawdown", "rebuild_cvar_5", "net_return_corr_vs_saved", "net_return_max_abs_error"], 1),
        "",
        "## Exact GGG Metrics Recomputed",
        "",
        md_table(pd.DataFrame([{**exact_metrics, **exposure_summary(weights)}]), ["ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_turnover", "cost_drag", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense"], 1),
        "",
        "## Confirmed Plumbing",
        "",
        "- Return alignment: `weekly_prices.pct_change().shift(-1)` on allocation-date index.",
        "- Turnover convention: one-way turnover `0.5 * sum(abs(diff(final_etf_weights)))`.",
        "- Cost convention: 10 bps times one-way turnover.",
        "- State labels: `data/04_layer2b_risk_regime_engine/market_state_history.csv`.",
        "- Offense exposure: sum of ETF columns in the project offense basket.",
        "- Defense/cash exposure: BIL plus defensive ETF basket; BIL is the explicit cash proxy.",
        "",
        "## State Labels",
        "",
        md_table(state_counts, ["market_state", "n_weeks"], 10),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c1_exact_ggg_baseline_note.md", lines)


def write_c2_insertion_audit(warnings: list[str]) -> None:
    rows = [
        {
            "insertion_point": "regime_multiplier_offset",
            "order": "inside overlay, before target-vol/cash budget finalization",
            "safe_inputs": "lagged breadth, macro stress, transition probability",
            "lookahead_risk": "low if inputs are tradable/lagged",
            "expected_effect": "small risky-budget confidence nudge",
            "danger": "can fight target-vol or add offense in stress",
            "stress_defense": "preserved only if no stress increase",
        },
        {
            "insertion_point": "offensive_sleeve_budget_offset",
            "order": "after state tilt, before final look-through",
            "safe_inputs": "offense eligibility, breadth, transition quality",
            "lookahead_risk": "low",
            "expected_effect": "change offense sleeve share without touching defense sleeves",
            "danger": "hidden beta increase",
            "stress_defense": "preserved if disabled in stressed_panic",
        },
        {
            "insertion_point": "defensive_sleeve_budget_offset",
            "order": "after state tilt, before overlay",
            "safe_inputs": "macro stress, deterioration, volatility pressure",
            "lookahead_risk": "low",
            "expected_effect": "increase defense budget in deterioration",
            "danger": "miss recovery re-risk",
            "stress_defense": "usually preserved",
        },
        {
            "insertion_point": "cash_BIL_budget_offset",
            "order": "overlay/cash budget step",
            "safe_inputs": "macro stress, target-vol binding, deterioration",
            "lookahead_risk": "low",
            "expected_effect": "cash absorbs confidence cuts",
            "danger": "cash drag in calm/recovery",
            "stress_defense": "preserved if asymmetric",
        },
        {
            "insertion_point": "rerisk_timing_offset",
            "order": "sleeve reallocation speed before overlay",
            "safe_inputs": "transition quality, breadth persistence",
            "lookahead_risk": "medium if transition labels not lagged",
            "expected_effect": "faster participation after confirmed broad transitions",
            "danger": "whipsaw",
            "stress_defense": "preserved if never used in stress",
        },
        {
            "insertion_point": "derisk_timing_offset",
            "order": "sleeve reallocation speed / overlay before look-through",
            "safe_inputs": "deterioration score, macro stress, dollar pressure",
            "lookahead_risk": "low",
            "expected_effect": "faster risk reduction in deteriorating environments",
            "danger": "false alarms reduce return",
            "stress_defense": "preserved or improved",
        },
        {
            "insertion_point": "transition_aware_smoothing",
            "order": "between state tilt and overlay",
            "safe_inputs": "state age, transition quality, breadth confirmation",
            "lookahead_risk": "medium; requires strict lag",
            "expected_effect": "avoid abrupt bad transitions",
            "danger": "late re-risk",
            "stress_defense": "preserved if stress entry remains fast",
        },
        {
            "insertion_point": "vol_target_aware_confidence",
            "order": "inside target-vol overlay interaction",
            "safe_inputs": "target-vol binding diagnostics, confidence",
            "lookahead_risk": "low if uses current allocation-date vol estimate",
            "expected_effect": "avoid adding risk when vol target already binds",
            "danger": "double-counting volatility pressure",
            "stress_defense": "preserved",
        },
        {
            "insertion_point": "sleeve_level_confidence_modifier",
            "order": "before ETF look-through",
            "safe_inputs": "sleeve role, breadth, macro stress",
            "lookahead_risk": "low",
            "expected_effect": "role-aware confidence changes",
            "danger": "requires exact sleeve-to-ETF reconstruction",
            "stress_defense": "depends on sleeve role controls",
        },
        {
            "insertion_point": "final_post_allocation_modifier",
            "order": "after final ETF weights",
            "safe_inputs": "all lagged confidence inputs",
            "lookahead_risk": "low",
            "expected_effect": "simple safety check/comparison",
            "danger": "not allocator-native; can violate overlay intent",
            "stress_defense": "preserved if disabled in stress",
        },
    ]
    audit = pd.DataFrame(rows)
    lines = [
        "# C2 Native Insertion Point Audit",
        "",
        "Research-only audit of possible confidence insertion points inside the GGG plumbing. This sprint tests small no-write proxies for the most relevant locations.",
        "",
        md_table(audit, ["insertion_point", "order", "safe_inputs", "lookahead_risk", "expected_effect", "danger", "stress_defense"], 20),
        "",
        "## Recommendation",
        "",
        "- Prefer regime/risky-budget, transition timing, and deterioration timing insertion points over final post-allocation scaling.",
        "- Final post-allocation bounded modifier is included only as a comparison because it was the best prior sandbox family.",
        "- A true production implementation would need a no-write wrapper around the allocator/overlay function, not edits to production artifacts.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c2_native_insertion_point_audit.md", lines)


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()
    NATIVE_OUT.mkdir(parents=True, exist_ok=True)

    weights = load_weights(GGG, warnings)
    if weights.empty:
        raise SystemExit("GGG weights missing; cannot align C3 confidence inputs.")

    scores = build_scores(weights.index, warnings)
    scores.to_csv(NATIVE_OUT / "c3_confidence_inputs.csv", index=False)

    missingness = (
        scores.drop(columns=["Date", "research_only"], errors="ignore")
        .isna()
        .mean()
        .reset_index()
        .rename(columns={"index": "field", 0: "missingness"})
    )
    score_summary = scores.describe(include="all").T.reset_index().rename(columns={"index": "field"})

    write_c1_baseline_note(warnings)
    write_c2_insertion_audit(warnings)

    lines = [
        "# C3 Confidence Inputs Report",
        "",
        "Research-only normalized confidence inputs aligned to the exact GGG weekly index.",
        "",
        "## Inputs Built",
        "",
        "- `breadth_confidence`: ETF 50d/200d and 13w/26w breadth blend.",
        "- `sector_confidence`: sector breadth blend.",
        "- `risk_on_confidence`: risk-on participation.",
        "- `macro_stress_filter`: VIX/credit/financial conditions stress filter, higher is safer.",
        "- `dollar_pressure_filter`: higher means less dollar pressure.",
        "- `transition_quality_score`: transition non-stress probability plus breadth/macro confirmation.",
        "- `combined_market_quality_score`: conservative blend of breadth, sector, risk-on, transition, macro, dollar, and signal agreement.",
        "- `offense_eligibility_score` and `deterioration_score`: diagnostic deployment features.",
        "",
        "## Missingness",
        "",
        md_table(missingness, ["field", "missingness"], 30),
        "",
        "## Score Summary",
        "",
        md_table(score_summary, ["field", "count", "mean", "std", "min", "25%", "50%", "75%", "max"], 30),
        "",
        "## Causality Notes",
        "",
        "- Existing Layer 1 signals use their `signal_value_tradable` columns where available.",
        "- Newly composed C3 scores are shifted by one week before use.",
        "- The scores are not optimized against returns.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c3_confidence_inputs_report.md", lines)

    print(f"Wrote {rel(NATIVE_OUT / 'c3_confidence_inputs.csv')} rows={len(scores)}")
    print(f"Wrote {rel(DOCS / 'c1_exact_ggg_baseline_note.md')}")
    print(f"Wrote {rel(DOCS / 'c2_native_insertion_point_audit.md')}")
    print(f"Wrote {rel(DOCS / 'c3_confidence_inputs_report.md')}")


if __name__ == "__main__":
    main()

