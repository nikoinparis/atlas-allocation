"""Frontier Phase 1A component diagnostics for state-quality composite.

Diagnostic-only. This script investigates why the first deployment quality
composite has negative IC in several states. It does not run wrapper
experiments and does not modify production, dashboard, public, or src files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs" / "research"
FRONTIER_OUT = DATA / "research" / "frontier_phase1"
SIGNALS_PATH = FRONTIER_OUT / "state_quality_signals.csv"
DAILY_PRICES = DATA / "01_data_hub" / "daily_prices.csv"

COMPONENTS = [
    "breadth_quality_score",
    "path_clarity_r2",
    "state_persistence_score",
    "credit_confirmation",
    "leadership_quality_score",
    "deployment_quality_composite",
]
BASE_COMPONENTS = COMPONENTS[:-1]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_signals() -> pd.DataFrame:
    if not SIGNALS_PATH.exists():
        raise SystemExit(f"Missing Phase 1A signals file: {rel(SIGNALS_PATH)}")
    df = pd.read_csv(SIGNALS_PATH)
    required = {"date", "market_state", *COMPONENTS}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"{rel(SIGNALS_PATH)} missing required columns: {', '.join(missing)}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["date"]).sort_values("date").set_index("date")
    for col in COMPONENTS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_spy_forward_return(index: pd.Index) -> pd.Series:
    if not DAILY_PRICES.exists():
        raise SystemExit(f"Missing actual price source used in Phase 1A: {rel(DAILY_PRICES)}")
    prices = pd.read_csv(DAILY_PRICES)
    if "Date" not in prices.columns or "SPY" not in prices.columns:
        raise SystemExit(f"{rel(DAILY_PRICES)} must contain Date and SPY columns.")
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce").dt.tz_localize(None)
    prices = prices.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    spy_weekly = pd.to_numeric(prices["SPY"], errors="coerce").resample("W-FRI").last().reindex(index).ffill()
    return spy_weekly.shift(-4) / spy_weekly - 1.0


def spearman_ic(x: pd.Series, y: pd.Series) -> float:
    clean = pd.concat([x, y], axis=1).dropna()
    if len(clean) < 10 or clean.iloc[:, 0].nunique() < 2 or clean.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(clean.iloc[:, 0].corr(clean.iloc[:, 1], method="spearman"))


def component_ic_table(signals: pd.DataFrame, forward_return: pd.Series) -> pd.DataFrame:
    rows = []
    for scope, group in [("full_period", signals)] + [(state, g) for state, g in signals.groupby("market_state")]:
        for component in COMPONENTS:
            clean = pd.concat([group[component], forward_return.reindex(group.index)], axis=1).dropna()
            rows.append(
                {
                    "scope": scope,
                    "market_state": "ALL" if scope == "full_period" else scope,
                    "component": component,
                    "spearman_ic": spearman_ic(group[component], forward_return.reindex(group.index)),
                    "n_observations": len(clean),
                    "mean_component": float(clean.iloc[:, 0].mean()) if len(clean) else np.nan,
                    "mean_forward_4w_return": float(clean.iloc[:, 1].mean()) if len(clean) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def quintile_table(signals: pd.DataFrame, forward_return: pd.Series) -> pd.DataFrame:
    rows = []
    for state, group in signals.groupby("market_state"):
        for component in COMPONENTS:
            frame = pd.DataFrame(
                {
                    "component_value": group[component],
                    "forward_return": forward_return.reindex(group.index),
                }
            ).dropna()
            if len(frame) < 25 or frame["component_value"].nunique() < 5:
                rows.append(
                    {
                        "market_state": state,
                        "component": component,
                        "quintile": "insufficient_data",
                        "n_observations": len(frame),
                        "mean_forward_4w_return": np.nan,
                        "median_component": np.nan,
                    }
                )
                continue
            try:
                frame["quintile"] = pd.qcut(frame["component_value"], 5, labels=[1, 2, 3, 4, 5], duplicates="drop")
            except ValueError:
                rows.append(
                    {
                        "market_state": state,
                        "component": component,
                        "quintile": "insufficient_data",
                        "n_observations": len(frame),
                        "mean_forward_4w_return": np.nan,
                        "median_component": np.nan,
                    }
                )
                continue
            for quintile, bucket in frame.groupby("quintile", observed=True):
                rows.append(
                    {
                        "market_state": state,
                        "component": component,
                        "quintile": str(quintile),
                        "n_observations": len(bucket),
                        "mean_forward_4w_return": float(bucket["forward_return"].mean()),
                        "median_component": float(bucket["component_value"].median()),
                    }
                )
    return pd.DataFrame(rows)


def correlation_matrices(signals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scopes = [("full_period", "ALL", signals)] + [(state, state, group) for state, group in signals.groupby("market_state")]
    for scope, state, group in scopes:
        clean = group[COMPONENTS].dropna(how="all")
        if len(clean) < 30:
            continue
        corr = clean.corr(method="spearman")
        for left in corr.index:
            for right in corr.columns:
                rows.append(
                    {
                        "scope": scope,
                        "market_state": state,
                        "component_1": left,
                        "component_2": right,
                        "spearman_corr": float(corr.loc[left, right]) if pd.notna(corr.loc[left, right]) else np.nan,
                        "n_observations": int(len(clean[[left, right]].dropna())),
                    }
                )
    return pd.DataFrame(rows)


def expanding_zscore(series: pd.Series, min_periods: int = 52) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    return ((s - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_variant_series(signals: pd.DataFrame, ic: pd.DataFrame) -> pd.DataFrame:
    full_ic = ic[ic["scope"].eq("full_period")].set_index("component")["spearman_ic"].to_dict()
    state_ic = ic[~ic["scope"].eq("full_period")]
    negative_state_counts = (
        state_ic.assign(is_negative=state_ic["spearman_ic"] < 0)
        .groupby("component")["is_negative"]
        .sum()
        .to_dict()
    )

    z = pd.DataFrame({component: expanding_zscore(signals[component]) for component in BASE_COMPONENTS}, index=signals.index)
    variants = pd.DataFrame(index=signals.index)
    variants["variant_a_original_equal_weight"] = signals["deployment_quality_composite"]

    signs_b = {component: -1.0 if full_ic.get(component, 0.0) < 0 else 1.0 for component in BASE_COMPONENTS}
    variants["variant_b_flip_negative_full_ic"] = pd.DataFrame({c: signs_b[c] * z[c] for c in BASE_COMPONENTS}).mean(axis=1)

    signs_c = {component: -1.0 if negative_state_counts.get(component, 0) >= 3 else 1.0 for component in BASE_COMPONENTS}
    variants["variant_c_flip_negative_3plus_states"] = pd.DataFrame({c: signs_c[c] * z[c] for c in BASE_COMPONENTS}).mean(axis=1)

    variants["variant_d_exclude_state_persistence"] = z[[c for c in BASE_COMPONENTS if c != "state_persistence_score"]].mean(axis=1)
    variants["variant_e_exclude_credit_confirmation"] = z[[c for c in BASE_COMPONENTS if c != "credit_confirmation"]].mean(axis=1)
    variants["variant_f_exclude_persistence_and_credit"] = z[
        [c for c in BASE_COMPONENTS if c not in {"state_persistence_score", "credit_confirmation"}]
    ].mean(axis=1)

    for col in variants.columns:
        if col != "variant_a_original_equal_weight":
            variants[col] = expanding_zscore(variants[col]).clip(-3.0, 3.0)
    return variants


def variant_ic_table(signals: pd.DataFrame, variants: pd.DataFrame, forward_return: pd.Series) -> pd.DataFrame:
    rows = []
    for scope, index in [("full_period", signals.index)] + [(state, group.index) for state, group in signals.groupby("market_state")]:
        for variant in variants.columns:
            x = variants.loc[index, variant]
            y = forward_return.reindex(index)
            clean = pd.concat([x, y], axis=1).dropna()
            rows.append(
                {
                    "scope": scope,
                    "market_state": "ALL" if scope == "full_period" else scope,
                    "variant": variant,
                    "spearman_ic": spearman_ic(x, y),
                    "n_observations": len(clean),
                    "mean_forward_4w_return": float(clean.iloc[:, 1].mean()) if len(clean) else np.nan,
                    "overfitting_warning": "diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals",
                }
            )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, columns: list[str], n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df[[c for c in columns if c in df.columns]].head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def write_report(ic: pd.DataFrame, quintiles: pd.DataFrame, correlations: pd.DataFrame, variant_ic: pd.DataFrame) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    full = ic[ic["scope"].eq("full_period")].sort_values("spearman_ic", ascending=False)
    state = ic[~ic["scope"].eq("full_period")]
    hurting = state[state["spearman_ic"] < 0].groupby("component").size().reset_index(name="negative_state_count")
    helping = state[state["spearman_ic"] > 0].groupby("component").size().reset_index(name="positive_state_count")
    variant_full = variant_ic[variant_ic["scope"].eq("full_period")].sort_values("spearman_ic", ascending=False)
    variant_states = variant_ic[~variant_ic["scope"].eq("full_period")]
    variant_summary = (
        variant_states.groupby("variant")
        .agg(
            mean_state_ic=("spearman_ic", "mean"),
            min_state_ic=("spearman_ic", "min"),
            positive_states=("spearman_ic", lambda x: int((x > 0).sum())),
            negative_states=("spearman_ic", lambda x: int((x < 0).sum())),
            total_state_obs=("n_observations", "sum"),
        )
        .reset_index()
        .sort_values(["positive_states", "mean_state_ic"], ascending=[False, False])
    )
    corr_with_composite = correlations[
        (correlations["scope"].eq("full_period"))
        & (correlations["component_2"].eq("deployment_quality_composite"))
        & (~correlations["component_1"].eq("deployment_quality_composite"))
    ].sort_values("spearman_corr", ascending=False)

    best_variant = variant_summary.head(1)
    recommendation = (
        "Do not proceed to Phase 1B with the original composite. Revise Phase 1A into a state-aware or sign-audited diagnostic first."
    )
    if not best_variant.empty and int(best_variant.iloc[0]["positive_states"]) >= 4:
        recommendation = (
            "Do not run wrapper diagnostics yet, but Phase 1A is worth revising around the best diagnostic variant with predeclared signs and fresh validation."
        )

    lines = [
        "# Frontier Phase 1A Component Diagnostics",
        "",
        "Diagnostic-only review of the first deployment-quality composite. No wrapper experiment was run.",
        "",
        "## Full-Period Component IC",
        "",
        markdown_table(full, ["component", "spearman_ic", "n_observations", "mean_component", "mean_forward_4w_return"], 10),
        "",
        "## Component IC By State",
        "",
        markdown_table(state.sort_values(["market_state", "spearman_ic"], ascending=[True, False]), ["market_state", "component", "spearman_ic", "n_observations"], 40),
        "",
        "## Helping Components",
        "",
        markdown_table(helping.sort_values("positive_state_count", ascending=False), ["component", "positive_state_count"], 10),
        "",
        "## Hurting Components",
        "",
        markdown_table(hurting.sort_values("negative_state_count", ascending=False), ["component", "negative_state_count"], 10),
        "",
        "## Composite Redundancy",
        "",
        "Full-period Spearman correlation versus the original composite:",
        "",
        markdown_table(corr_with_composite, ["component_1", "spearman_corr", "n_observations"], 10),
        "",
        "## Diagnostic Composite Variants",
        "",
        markdown_table(variant_summary, ["variant", "mean_state_ic", "min_state_ic", "positive_states", "negative_states", "total_state_obs"], 10),
        "",
        "Full-period variant IC:",
        "",
        markdown_table(variant_full, ["variant", "spearman_ic", "n_observations", "overfitting_warning"], 10),
        "",
        "## Monotonicity Sample",
        "",
        markdown_table(quintiles, ["market_state", "component", "quintile", "n_observations", "mean_forward_4w_return", "median_component"], 30),
        "",
        "## Diagnosis",
        "",
        "- The negative IC is not assumed to be proof against every component; it can reflect sign errors, state dependence, redundancy, or a design that rewards late-cycle maturity rather than forward opportunity.",
        "- Variant sign flips and exclusions are diagnostics only. They use full-history IC and therefore carry overfitting risk.",
        "- The original composite should not be passed into the wrapper until signs and state behavior are predeclared and revalidated.",
        "",
        "## Explicit Recommendation",
        "",
        recommendation,
    ]
    (DOCS / "frontier_phase1_component_diagnostics.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    FRONTIER_OUT.mkdir(parents=True, exist_ok=True)
    signals = load_signals()
    forward_return = load_spy_forward_return(signals.index)
    ic = component_ic_table(signals, forward_return)
    quintiles = quintile_table(signals, forward_return)
    correlations = correlation_matrices(signals)
    variants = build_variant_series(signals, ic)
    variant_ic = variant_ic_table(signals, variants, forward_return)

    ic.to_csv(FRONTIER_OUT / "component_ic_by_state.csv", index=False)
    quintiles.to_csv(FRONTIER_OUT / "component_quintile_returns_by_state.csv", index=False)
    correlations.to_csv(FRONTIER_OUT / "component_correlation_matrix.csv", index=False)
    variant_ic.to_csv(FRONTIER_OUT / "composite_variant_ic_by_state.csv", index=False)
    write_report(ic, quintiles, correlations, variant_ic)

    best = (
        variant_ic[~variant_ic["scope"].eq("full_period")]
        .groupby("variant")
        .agg(mean_state_ic=("spearman_ic", "mean"), positive_states=("spearman_ic", lambda x: int((x > 0).sum())))
        .reset_index()
        .sort_values(["positive_states", "mean_state_ic"], ascending=[False, False])
        .head(1)
    )

    print("Frontier Phase 1A Component Diagnostics")
    print(f"Created: {rel(FRONTIER_OUT / 'component_ic_by_state.csv')}")
    print(f"Created: {rel(FRONTIER_OUT / 'component_quintile_returns_by_state.csv')}")
    print(f"Created: {rel(FRONTIER_OUT / 'component_correlation_matrix.csv')}")
    print(f"Created: {rel(FRONTIER_OUT / 'composite_variant_ic_by_state.csv')}")
    print(f"Created: {rel(DOCS / 'frontier_phase1_component_diagnostics.md')}")
    print("")
    print("Component IC by state:")
    print(ic[~ic["scope"].eq("full_period")].to_string(index=False))
    print("")
    print("Full-period component IC:")
    print(ic[ic["scope"].eq("full_period")].to_string(index=False))
    print("")
    if not best.empty:
        print(
            "Best diagnostic variant: "
            f"{best.iloc[0]['variant']} mean_state_ic={best.iloc[0]['mean_state_ic']:.4f} "
            f"positive_states={int(best.iloc[0]['positive_states'])}"
        )
    print("Recommendation: Do not move to Phase 1B with the original composite; revise/sign-audit Phase 1A first.")


if __name__ == "__main__":
    main()
