"""Path 3.2 transition-quality analysis.

Research-only diagnostic. Tests whether transitions into calm/recovery states
look strong, broad, weak, or deteriorating using the Path 3 market-quality
state estimates. No allocation logic is changed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    HUB,
    PATH3_OUT,
    ensure_dirs,
    future_drawdown,
    future_return,
    load_next_week_returns,
    load_returns,
    load_states,
    md_table,
    read_csv,
    rel,
    write_text,
)


GOOD_STATES = {"calm_trend", "recovery_fragile", "recovery_confirmed"}


def quality_bucket(row: pd.Series) -> str:
    if row["deterioration_score"] >= 0.68:
        return "deteriorating"
    if row["transition_quality_score"] >= 0.68 and row["participation_quality_score"] >= 0.55:
        return "strong_broad"
    if row["transition_quality_score"] >= 0.55:
        return "constructive"
    if row["participation_quality_score"] <= 0.40 or row["signal_dispersion_score"] >= 0.68:
        return "weak_choppy"
    return "mixed"


def window_state_flags(states: pd.Series, date: pd.Timestamp, horizon: int) -> dict[str, float]:
    if date not in states.index:
        return {"stress_within_horizon": np.nan, "good_state_persistence": np.nan, "state_changes": np.nan}
    loc = states.index.get_loc(date)
    if isinstance(loc, slice):
        loc = loc.start
    window = states.iloc[loc : loc + horizon]
    if len(window) < horizon:
        return {"stress_within_horizon": np.nan, "good_state_persistence": np.nan, "state_changes": np.nan}
    current = str(states.loc[date])
    return {
        "stress_within_horizon": float(window.eq("stressed_panic").any()),
        "good_state_persistence": float(window.isin(GOOD_STATES).mean()),
        "state_changes": float(window.ne(current).sum()),
    }


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    quality_path = PATH3_OUT / "market_quality_states.csv"
    q = read_csv(quality_path, warnings)
    if q.empty:
        raise SystemExit("market_quality_states.csv missing; run build_market_quality_state_model.py first.")
    q["Date"] = pd.to_datetime(q["Date"], errors="coerce")
    q = q.dropna(subset=["Date"]).set_index("Date").sort_index()

    states = load_states(warnings)
    returns = load_returns(GGG, warnings)
    next_returns = load_next_week_returns(warnings)
    if states.empty or returns.empty:
        raise SystemExit("Market states or GGG returns missing; cannot run transition analysis.")

    state_series = states["market_state"].reindex(q.index).ffill()
    ggg_ret = returns["net_return"].reindex(q.index)
    spy_ret = next_returns.get("SPY", pd.Series(index=q.index, dtype=float)).reindex(q.index)
    q["future_4w_ggg_return"] = future_return(ggg_ret, 4)
    q["future_8w_ggg_return"] = future_return(ggg_ret, 8)
    q["future_4w_spy_return"] = future_return(spy_ret, 4)
    q["future_4w_ggg_drawdown"] = future_drawdown(ggg_ret, 4)

    prior_state = state_series.shift(1)
    transition_mask = state_series.ne(prior_state) & state_series.isin(GOOD_STATES)
    rows = []
    for date in q.index[transition_mask.fillna(False)]:
        row = q.loc[date]
        flags4 = window_state_flags(state_series, date, 4)
        flags8 = window_state_flags(state_series, date, 8)
        target = str(state_series.loc[date])
        bucket = quality_bucket(row)
        future4 = float(row.get("future_4w_ggg_return", np.nan))
        future8 = float(row.get("future_8w_ggg_return", np.nan))
        stress8 = flags8["stress_within_horizon"]
        whipsaw = float(flags4["state_changes"] > 1 or flags4["stress_within_horizon"] > 0)
        failed = float((np.isfinite(future4) and future4 < 0) or (np.isfinite(stress8) and stress8 > 0))
        rows.append(
            {
                "Date": date,
                "from_state": str(prior_state.loc[date]),
                "to_state": target,
                "transition_quality_bucket": bucket,
                "offense_confidence_score": float(row["offense_confidence_score"]),
                "deterioration_score": float(row["deterioration_score"]),
                "participation_quality_score": float(row["participation_quality_score"]),
                "transition_quality_score": float(row["transition_quality_score"]),
                "risk_appetite_score": float(row["risk_appetite_score"]),
                "future_4w_ggg_return": future4,
                "future_8w_ggg_return": future8,
                "future_4w_spy_return": float(row.get("future_4w_spy_return", np.nan)),
                "future_4w_ggg_drawdown": float(row.get("future_4w_ggg_drawdown", np.nan)),
                "stress_within_4w": flags4["stress_within_horizon"],
                "stress_within_8w": flags8["stress_within_horizon"],
                "good_state_persistence_4w": flags4["good_state_persistence"],
                "state_changes_4w": flags4["state_changes"],
                "whipsaw_4w": whipsaw,
                "transition_success_4w": float((not failed) and whipsaw == 0 and np.isfinite(future4) and future4 > 0),
                "false_calm_trend_flag": float(target == "calm_trend" and ((np.isfinite(future4) and future4 < 0) or (np.isfinite(stress8) and stress8 > 0))),
                "failed_recovery_flag": float(target.startswith("recovery") and failed),
                "research_only": True,
            }
        )

    results = pd.DataFrame(rows)
    results.to_csv(PATH3_OUT / "transition_quality_results.csv", index=False)

    summary = (
        results.groupby(["to_state", "transition_quality_bucket"])
        .agg(
            n_transitions=("Date", "count"),
            success_rate_4w=("transition_success_4w", "mean"),
            whipsaw_rate_4w=("whipsaw_4w", "mean"),
            stress_rate_8w=("stress_within_8w", "mean"),
            avg_future_4w_ggg_return=("future_4w_ggg_return", "mean"),
            avg_future_4w_drawdown=("future_4w_ggg_drawdown", "mean"),
        )
        .reset_index()
        if not results.empty
        else pd.DataFrame()
    )

    stress_entries = state_series.eq("stressed_panic") & state_series.shift(1).ne("stressed_panic")
    lead_rows = []
    for date in q.index[stress_entries.reindex(q.index).fillna(False)]:
        loc = q.index.get_loc(date)
        if isinstance(loc, slice):
            loc = loc.start
        prior = q.iloc[max(0, loc - 8) : loc]
        if prior.empty:
            continue
        high_det = prior[prior["deterioration_score"] >= 0.65]
        lead_rows.append(
            {
                "stress_entry_date": date,
                "max_prior_8w_deterioration": float(prior["deterioration_score"].max()),
                "weeks_with_prior_deterioration": int(len(high_det)),
                "first_warning_lead_weeks": int((date - high_det.index[0]).days / 7) if not high_det.empty else np.nan,
            }
        )
    lead = pd.DataFrame(lead_rows)

    lines = [
        "# Path 3 Transition Quality Report",
        "",
        "Research-only diagnostic of whether calm/recovery transitions are strong, fragile, broad, weak, or deteriorating.",
        "",
        "## Transition Summary",
        "",
        md_table(summary.sort_values(["to_state", "success_rate_4w"], ascending=[True, False]) if not summary.empty else summary, ["to_state", "transition_quality_bucket", "n_transitions", "success_rate_4w", "whipsaw_rate_4w", "stress_rate_8w", "avg_future_4w_ggg_return", "avg_future_4w_drawdown"], 20),
        "",
        "## Recent / Largest Weak Transitions",
        "",
        md_table(results.sort_values(["whipsaw_4w", "future_4w_ggg_return"], ascending=[False, True]), ["Date", "from_state", "to_state", "transition_quality_bucket", "future_4w_ggg_return", "whipsaw_4w", "stress_within_8w", "deterioration_score"], 12),
        "",
        "## Deterioration Lead-Time Before Stressed Panic",
        "",
        md_table(lead, ["stress_entry_date", "max_prior_8w_deterioration", "weeks_with_prior_deterioration", "first_warning_lead_weeks"], 12),
        "",
        "## Interpretation",
        "",
        "- Transition-quality modeling is promising if strong/broad transitions have higher success and lower whipsaw than weak/choppy or deteriorating transitions.",
        "- These are diagnostics only; they do not optimize allocations or promote a rule.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path3_transition_quality_report.md", lines)

    print(f"Wrote {rel(PATH3_OUT / 'transition_quality_results.csv')} rows={len(results)}")
    print(f"Wrote {rel(DOCS / 'path3_transition_quality_report.md')}")


if __name__ == "__main__":
    main()

