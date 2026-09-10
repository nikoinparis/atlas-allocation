"""Path 3.1 interpretable market-quality state model.

Research-only environment estimation. The score is not fitted to returns; it is
a causal blend of existing breadth, macro, dollar, and signal-quality features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    PATH3_OUT,
    ensure_dirs,
    future_drawdown,
    future_return,
    load_market_quality_inputs,
    load_returns,
    load_weights,
    md_table,
    rel,
    write_text,
)


def assign_state(row: pd.Series) -> str:
    if row["deterioration_score"] >= 0.72:
        return "defensive_deteriorating"
    if row["offense_confidence_score"] >= 0.72 and row["deterioration_score"] <= 0.42:
        return "high_confidence_offense"
    if row["transition_quality_score"] >= 0.68 and row["participation_quality_score"] >= 0.55:
        return "constructive_transition"
    if row["participation_quality_score"] <= 0.38 or row["signal_dispersion_score"] >= 0.68:
        return "fragile_or_choppy"
    return "neutral_quality"


def build_quality_model(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    inputs = load_market_quality_inputs(index, warnings)
    out = pd.DataFrame(index=index)

    out["etf_breadth_score"] = inputs[
        ["bm_etf_above_50d_ma", "bm_etf_above_200d_ma", "bm_etf_positive_13w_mom", "bm_etf_positive_26w_mom"]
    ].mean(axis=1)
    out["sector_breadth_score"] = inputs[
        ["bm_sector_above_50d_ma", "bm_sector_above_200d_ma", "bm_sector_positive_13w_mom", "bm_sector_positive_26w_mom"]
    ].mean(axis=1)
    out["risk_on_participation_score"] = inputs["bm_risk_on_participation"]
    out["breadth_persistence_score"] = out["etf_breadth_score"].rolling(6, min_periods=2).mean().fillna(out["etf_breadth_score"])
    out["breadth_deterioration_score"] = (0.5 - out["etf_breadth_score"].diff(4)).clip(0, 1).fillna(0.5)
    out["dollar_pressure_score"] = inputs["bm_dollar_strength_blended"]
    out["vix_pressure_score"] = (1.0 - inputs["r2_vix_term_structure"]).clip(0, 1)
    out["credit_pressure_score"] = (1.0 - inputs["r2_credit_spread"]).clip(0, 1)
    out["financial_conditions_pressure_score"] = (1.0 - inputs["r2_financial_conditions"]).clip(0, 1)
    out["signal_agreement_score"] = inputs["bm_quality_signal_agreement"]
    out["signal_dispersion_score"] = inputs["bm_quality_signal_dispersion"]
    out["existing_deterioration_warning_score"] = inputs["bm_quality_deterioration_warning"]
    out["breadth_confirmation_score"] = inputs["bm_quality_breadth_confirmation"]

    out["participation_quality_score"] = (
        0.35 * out["etf_breadth_score"]
        + 0.30 * out["sector_breadth_score"]
        + 0.25 * out["risk_on_participation_score"]
        + 0.10 * out["breadth_persistence_score"]
    ).clip(0, 1)
    out["deterioration_score"] = (
        0.22 * (1.0 - out["etf_breadth_score"])
        + 0.15 * (1.0 - out["sector_breadth_score"])
        + 0.16 * out["breadth_deterioration_score"]
        + 0.14 * out["dollar_pressure_score"]
        + 0.12 * out["vix_pressure_score"]
        + 0.10 * out["credit_pressure_score"]
        + 0.06 * out["signal_dispersion_score"]
        + 0.05 * out["existing_deterioration_warning_score"]
    ).clip(0, 1)
    out["offense_confidence_score"] = (
        0.45 * out["participation_quality_score"]
        + 0.25 * out["signal_agreement_score"]
        + 0.15 * out["breadth_confirmation_score"]
        + 0.15 * (1.0 - out["deterioration_score"])
    ).clip(0, 1)
    transition_prior = pd.to_numeric(inputs.get("transition_non_stress_prob", pd.Series(index=index)), errors="coerce").reindex(index)
    transition_prior = transition_prior.fillna(transition_prior.expanding(min_periods=20).median()).fillna(0.5).clip(0, 1)
    out["transition_quality_score"] = (
        0.40 * transition_prior
        + 0.25 * out["participation_quality_score"]
        + 0.20 * (1.0 - out["deterioration_score"])
        + 0.15 * (1.0 - out["signal_dispersion_score"])
    ).clip(0, 1)
    out["risk_appetite_score"] = (
        0.50 * out["offense_confidence_score"]
        + 0.30 * out["transition_quality_score"]
        + 0.20 * (1.0 - out["deterioration_score"])
    ).clip(0, 1)
    out["market_quality_state"] = out.apply(assign_state, axis=1)

    for col in ["market_state", "risk_state", "market_drawdown", "transition_non_stress_prob", "transition_good_state_prob"]:
        if col in inputs.columns:
            out[col] = inputs[col]

    out = out.reset_index().rename(columns={"index": "Date"})
    out.insert(1, "research_only", True)
    return out


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    weights = load_weights(GGG, warnings)
    returns = load_returns(GGG, warnings)
    if weights.empty:
        raise SystemExit("GGG weights missing; cannot align market-quality states.")

    quality = build_quality_model(weights.index, warnings)
    if not returns.empty:
        ret = returns["net_return"].reindex(pd.to_datetime(quality["Date"]))
        quality["future_4w_ggg_return"] = future_return(ret, 4).values
        quality["future_8w_ggg_return"] = future_return(ret, 8).values
        quality["future_4w_ggg_drawdown"] = future_drawdown(ret, 4).values

    quality.to_csv(PATH3_OUT / "market_quality_states.csv", index=False)

    state_summary = (
        quality.groupby("market_quality_state")
        .agg(
            n_weeks=("Date", "count"),
            avg_offense_confidence=("offense_confidence_score", "mean"),
            avg_deterioration=("deterioration_score", "mean"),
            avg_transition_quality=("transition_quality_score", "mean"),
            avg_future_4w_ggg_return=("future_4w_ggg_return", "mean") if "future_4w_ggg_return" in quality.columns else ("offense_confidence_score", "mean"),
            avg_future_4w_ggg_drawdown=("future_4w_ggg_drawdown", "mean") if "future_4w_ggg_drawdown" in quality.columns else ("deterioration_score", "mean"),
        )
        .reset_index()
        .sort_values("avg_offense_confidence", ascending=False)
    )

    by_market_state = (
        quality.groupby(["market_state", "market_quality_state"]).size().reset_index(name="n_weeks")
        if "market_state" in quality.columns
        else pd.DataFrame()
    )

    lines = [
        "# Path 3 Market Quality State Report",
        "",
        "Research-only interpretable confidence-state model. Scores are blended from existing tradable/lagged breadth, macro, dollar, and signal-quality signals; no return optimization was used.",
        "",
        "## State Summary",
        "",
        md_table(state_summary, ["market_quality_state", "n_weeks", "avg_offense_confidence", "avg_deterioration", "avg_transition_quality", "avg_future_4w_ggg_return", "avg_future_4w_ggg_drawdown"], 10),
        "",
        "## Market State Cross-Tab",
        "",
        md_table(by_market_state.sort_values(["market_state", "n_weeks"], ascending=[True, False]), ["market_state", "market_quality_state", "n_weeks"], 20),
        "",
        "## Interpretation",
        "",
        "- The model is intended as environment estimation, not alpha.",
        "- The key research question is whether breadth/macro/dollar information should control offense confidence and transition timing rather than directly scaling final ETF weights.",
        "- Use later scripts to test transition quality, offense eligibility, and a very light sandbox.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path3_market_quality_state_report.md", lines)

    print(f"Wrote {rel(PATH3_OUT / 'market_quality_states.csv')} rows={len(quality)}")
    print(f"Wrote {rel(DOCS / 'path3_market_quality_state_report.md')}")


if __name__ == "__main__":
    main()

