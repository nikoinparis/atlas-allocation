"""Path 3.3 offense eligibility research.

Research-only diagnostics. Tests simple confidence/market-quality eligibility
rules and measures how often they would allow, suppress, or bound offense. This
does not directly optimize or alter production allocations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    OFFENSE,
    PATH3_OUT,
    ensure_dirs,
    future_drawdown,
    future_return,
    load_returns,
    load_states,
    load_weights,
    md_table,
    read_csv,
    rel,
    write_text,
)


def whipsaw_flags(states: pd.Series, horizon: int = 4) -> pd.Series:
    out = pd.Series(index=states.index, dtype=float)
    for i, date in enumerate(states.index):
        window = states.iloc[i : i + horizon]
        if len(window) < horizon:
            out.loc[date] = np.nan
            continue
        current = str(states.loc[date])
        out.loc[date] = float(window.ne(current).sum() > 1 or window.eq("stressed_panic").any())
    return out


def build_rules(q: pd.DataFrame) -> dict[str, pd.Series]:
    state = q.get("market_state", pd.Series("", index=q.index)).astype(str)
    recovery = state.isin(["recovery_fragile", "recovery_confirmed"])
    calm_neutral = state.isin(["calm_trend", "neutral_mixed"])
    stress = state.eq("stressed_panic")
    return {
        "broad_breadth_low_deterioration": (q["participation_quality_score"] >= 0.50) & (q["deterioration_score"] <= 0.60) & ~stress,
        "transition_quality_stable": (q["transition_quality_score"] >= 0.58) & (q["deterioration_score"] <= 0.65) & ~stress,
        "risk_appetite_positive": (q["risk_appetite_score"] >= 0.58) & ~stress,
        "strict_all_clear": (
            (q["participation_quality_score"] >= 0.55)
            & (q["deterioration_score"] <= 0.55)
            & (q["dollar_pressure_score"] <= 0.70)
            & (q["risk_appetite_score"] >= 0.60)
            & ~stress
        ),
        "deterioration_suppression_only": (q["deterioration_score"] <= 0.68) & ~stress,
        "recovery_asymmetric_permission": (
            (calm_neutral & (q["risk_appetite_score"] >= 0.55))
            | (recovery & (q["transition_quality_score"] >= 0.55) & (q["deterioration_score"] <= 0.70))
        )
        & ~stress,
    }


def summarize_rule(rule: str, allowed: pd.Series, panel: pd.DataFrame, state_name: str | None = None) -> dict[str, float | str]:
    data = panel.copy()
    if state_name is not None:
        data = data[data["market_state"].eq(state_name)]
    if data.empty:
        return {"rule_name": rule, "market_state": state_name or "ALL", "n_weeks": 0}
    allow = allowed.reindex(data.index).fillna(False).astype(bool)
    suppressed = ~allow
    row: dict[str, float | str] = {
        "rule_name": rule,
        "market_state": state_name or "ALL",
        "n_weeks": int(len(data)),
        "allowed_share": float(allow.mean()),
        "suppressed_share": float(suppressed.mean()),
        "avg_actual_offense_when_allowed": float(data.loc[allow, "actual_offense"].mean()) if allow.any() else np.nan,
        "avg_actual_offense_when_suppressed": float(data.loc[suppressed, "actual_offense"].mean()) if suppressed.any() else np.nan,
        "future_4w_return_allowed": float(data.loc[allow, "future_4w_ggg_return"].mean()) if allow.any() else np.nan,
        "future_4w_return_suppressed": float(data.loc[suppressed, "future_4w_ggg_return"].mean()) if suppressed.any() else np.nan,
        "future_4w_drawdown_allowed": float(data.loc[allow, "future_4w_ggg_drawdown"].mean()) if allow.any() else np.nan,
        "future_4w_drawdown_suppressed": float(data.loc[suppressed, "future_4w_ggg_drawdown"].mean()) if suppressed.any() else np.nan,
        "whipsaw_rate_allowed": float(data.loc[allow, "whipsaw_4w"].mean()) if allow.any() else np.nan,
        "whipsaw_rate_suppressed": float(data.loc[suppressed, "whipsaw_4w"].mean()) if suppressed.any() else np.nan,
        "avg_risk_appetite_allowed": float(data.loc[allow, "risk_appetite_score"].mean()) if allow.any() else np.nan,
        "avg_deterioration_suppressed": float(data.loc[suppressed, "deterioration_score"].mean()) if suppressed.any() else np.nan,
        "research_only": True,
    }
    row["future_return_lift_allowed_minus_suppressed"] = (
        row["future_4w_return_allowed"] - row["future_4w_return_suppressed"]
        if np.isfinite(row["future_4w_return_allowed"]) and np.isfinite(row["future_4w_return_suppressed"])
        else np.nan
    )
    return row


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    q = read_csv(PATH3_OUT / "market_quality_states.csv", warnings)
    if q.empty:
        raise SystemExit("market_quality_states.csv missing; run build_market_quality_state_model.py first.")
    q["Date"] = pd.to_datetime(q["Date"], errors="coerce")
    q = q.dropna(subset=["Date"]).set_index("Date").sort_index()

    weights = load_weights(GGG, warnings)
    returns = load_returns(GGG, warnings)
    states = load_states(warnings)
    if weights.empty or returns.empty or states.empty:
        raise SystemExit("Required weights, returns, or states missing.")

    offense_cols = [c for c in weights.columns if c in OFFENSE]
    panel = q.copy()
    panel["market_state"] = states["market_state"].reindex(panel.index).ffill()
    panel["actual_offense"] = weights.reindex(panel.index)[offense_cols].sum(axis=1)
    panel["future_4w_ggg_return"] = future_return(returns["net_return"].reindex(panel.index), 4)
    panel["future_8w_ggg_return"] = future_return(returns["net_return"].reindex(panel.index), 8)
    panel["future_4w_ggg_drawdown"] = future_drawdown(returns["net_return"].reindex(panel.index), 4)
    panel["whipsaw_4w"] = whipsaw_flags(panel["market_state"], 4)

    rules = build_rules(panel)
    rows = []
    states_list = ["calm_trend", "neutral_mixed", "recovery_fragile", "recovery_confirmed", "stressed_panic"]
    for rule, allowed in rules.items():
        rows.append(summarize_rule(rule, allowed, panel))
        for state_name in states_list:
            rows.append(summarize_rule(rule, allowed, panel, state_name))

    results = pd.DataFrame(rows)
    results.to_csv(PATH3_OUT / "offense_eligibility_results.csv", index=False)

    overall = results[results["market_state"].eq("ALL")].sort_values("future_return_lift_allowed_minus_suppressed", ascending=False)
    calm = results[results["market_state"].eq("calm_trend")].sort_values("future_return_lift_allowed_minus_suppressed", ascending=False)
    stress = results[results["market_state"].eq("stressed_panic")]

    lines = [
        "# Path 3 Offense Eligibility Report",
        "",
        "Research-only diagnostic of whether offense should be allowed, suppressed, or bounded based on market-quality states.",
        "",
        "## Overall Rule Diagnostics",
        "",
        md_table(overall, ["rule_name", "allowed_share", "suppressed_share", "future_4w_return_allowed", "future_4w_return_suppressed", "future_return_lift_allowed_minus_suppressed", "whipsaw_rate_allowed", "whipsaw_rate_suppressed"], 10),
        "",
        "## Calm Trend Diagnostics",
        "",
        md_table(calm, ["rule_name", "allowed_share", "suppressed_share", "future_4w_return_allowed", "future_4w_return_suppressed", "future_return_lift_allowed_minus_suppressed", "whipsaw_rate_allowed"], 10),
        "",
        "## Stressed Panic Behavior",
        "",
        md_table(stress, ["rule_name", "allowed_share", "suppressed_share", "future_4w_return_allowed", "future_4w_return_suppressed", "whipsaw_rate_allowed"], 10),
        "",
        "## Interpretation",
        "",
        "- Useful eligibility rules should suppress low-quality weeks without suppressing too much calm_trend or recovery participation.",
        "- Stronger future-return lift and lower whipsaw for allowed weeks suggests the confidence signal may be better used as offense permission than direct final-weight alpha.",
        "- These rules are diagnostics only and are not production allocation logic.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path3_offense_eligibility_report.md", lines)

    print(f"Wrote {rel(PATH3_OUT / 'offense_eligibility_results.csv')} rows={len(results)}")
    print(f"Wrote {rel(DOCS / 'path3_offense_eligibility_report.md')}")


if __name__ == "__main__":
    main()

