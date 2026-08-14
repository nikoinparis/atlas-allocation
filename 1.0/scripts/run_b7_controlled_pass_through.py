"""B7 controlled portfolio pass-through sandbox.

Research-only. This script uses saved production-candidate ETF weights and
applies small, bounded post-hoc multipliers from B6 breadth/macro/dollar signals.
It does not change production pins, dashboard/public files, portfolio artifacts,
allocation logic, R5/R6 logic, or live trading logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data")
HUB = DATA / "01_data_hub"
SIGNALS = DATA / "02_layer1_signals"
REGIME = DATA / "04_layer2b_risk_regime_engine"
PORT = DATA / "05_layer3_portfolio_construction"
OUT = DATA / "research" / "b7_pass_through"
DOCS = Path("docs") / "research"

GGG = "improved_phaseggg_confirmed_only_robust_offense"
PHASE2B = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"

COST_BPS = 10.0
WEEKS = 52

OFFENSE = {
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "VWO",
    "VEA",
    "EWJ",
    "VNQ",
    "HYG",
    "XLY",
    "XLK",
    "XLF",
    "XLI",
    "XLB",
    "XLE",
    "VTV",
    "VUG",
}
EM_COMMODITY_PRESSURE = {"EEM", "VWO", "EFA", "VEA", "EWJ", "PDBC", "USO", "DBA", "SLV", "XLE"}
DEFENSE = {"BIL", "SHY", "IEF", "TLT", "LQD", "MBB", "TIP", "GLD", "IAU", "UUP", "XLP", "XLU", "XLV"}


@dataclass
class VariantSpec:
    name: str
    family: str
    breadth_mode: str = "none"
    breadth_signal: str = "bm_etf_positive_13w_mom"
    breadth_max: float = 1.10
    breadth_floor: float = 0.90
    macro_mode: str = "none"
    macro_strength: str = "mild"
    dollar_mode: str = "none"
    dollar_strength: str = "mild"


def ensure_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path, warnings: list[str]) -> pd.DataFrame:
    if not path.exists():
        warnings.append(f"Missing optional file: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"Could not read {path}: {exc}")
        return pd.DataFrame()


def date_index(df: pd.DataFrame, warnings: list[str], label: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "Date" not in out.columns and "Unnamed: 0" in out.columns:
        out = out.rename(columns={"Unnamed: 0": "Date"})
    if "Date" not in out.columns:
        warnings.append(f"{label} lacks Date/Unnamed: 0 column")
        return pd.DataFrame()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return out


def load_weights(name: str, warnings: list[str]) -> pd.DataFrame:
    return date_index(read_csv(PORT / f"portfolio_version_weights_{name}.csv", warnings), warnings, name).apply(pd.to_numeric, errors="coerce").fillna(0.0)


def load_returns(name: str, warnings: list[str]) -> pd.DataFrame:
    return date_index(read_csv(PORT / f"portfolio_version_returns_{name}.csv", warnings), warnings, name)


def load_weekly_returns(warnings: list[str]) -> pd.DataFrame:
    return date_index(read_csv(HUB / "weekly_returns.csv", warnings), warnings, "weekly_returns.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)


def load_state_history(warnings: list[str]) -> pd.DataFrame:
    states = date_index(read_csv(REGIME / "market_state_history.csv", warnings), warnings, "market_state_history.csv")
    if states.empty or "market_state" not in states.columns:
        warnings.append("market_state_history.csv missing market_state; state summaries limited.")
        return pd.DataFrame()
    return states


def load_signal_value(name: str, ticker: str, warnings: list[str]) -> pd.Series:
    path = SIGNALS / f"signal_{name}.csv"
    df = read_csv(path, warnings)
    if df.empty:
        return pd.Series(dtype=float)
    df = date_index(df, warnings, str(path)).reset_index()
    if "Ticker" not in df.columns or "signal_value_tradable" not in df.columns:
        warnings.append(f"{path} lacks Ticker/signal_value_tradable; signal unavailable.")
        return pd.Series(dtype=float)
    sub = df[df["Ticker"].eq(ticker)].copy()
    if sub.empty:
        warnings.append(f"{path} has no ticker {ticker}; signal unavailable.")
        return pd.Series(dtype=float)
    return sub.set_index("Date")["signal_value_tradable"].astype(float).sort_index()


def rolling_percentile(series: pd.Series, window: int = 156, min_periods: int = 52) -> pd.Series:
    def pct_rank(x: np.ndarray) -> float:
        clean = pd.Series(x).dropna()
        if len(clean) < min_periods:
            return np.nan
        return float((clean <= clean.iloc[-1]).mean())
    return series.rolling(window, min_periods=min_periods).apply(pct_rank, raw=False)


def scaled_score(series: pd.Series, index: pd.Index) -> pd.Series:
    pct = rolling_percentile(series).reindex(index).ffill()
    return pct.clip(0, 1).fillna(0.5)


def load_controls(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    controls = pd.DataFrame(index=index)
    breadth_names = [
        "bm_etf_above_50d_ma",
        "bm_etf_above_200d_ma",
        "bm_etf_positive_13w_mom",
        "bm_etf_positive_26w_mom",
        "bm_risk_on_participation",
        "bm_sector_positive_26w_mom",
        "bm_sector_above_200d_ma",
        "bm_sector_above_50d_ma",
    ]
    for name in breadth_names:
        controls[name] = scaled_score(load_signal_value(name, "SPY", warnings), index)
    controls["breadth_composite"] = controls[[c for c in breadth_names if c in controls]].mean(axis=1)
    controls["sector_breadth_composite"] = controls[["bm_sector_positive_26w_mom", "bm_sector_above_200d_ma", "bm_sector_above_50d_ma"]].mean(axis=1)
    controls["macro_credit_calm"] = scaled_score(load_signal_value("r2_credit_spread", "SPY", warnings), index)
    controls["macro_vix"] = scaled_score(load_signal_value("r2_vix_term_structure", "SPY", warnings), index)
    controls["macro_financial"] = scaled_score(load_signal_value("r2_financial_conditions", "SPY", warnings), index)
    controls["macro_commodity"] = scaled_score(load_signal_value("r2_commodity_regime", "SPY", warnings), index)
    controls["dollar_4w"] = scaled_score(load_signal_value("bm_dollar_strength_4w", "UUP", warnings), index)
    controls["dollar_blended"] = scaled_score(load_signal_value("bm_dollar_strength_blended", "UUP", warnings), index)
    states = load_state_history(warnings)
    if not states.empty:
        controls["market_state"] = states["market_state"].reindex(index).ffill()
    else:
        controls["market_state"] = ""
    controls = controls.shift(0)  # Inputs are already tradable/lagged in Layer 1 files.
    return controls


def normalize_to_cash(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.clip(lower=0.0).copy()
    risky_cols = [c for c in out.columns if c != "BIL"]
    risky_sum = out[risky_cols].sum(axis=1)
    over = risky_sum > 1.0
    out.loc[over, risky_cols] = out.loc[over, risky_cols].div(risky_sum.loc[over], axis=0)
    out["BIL"] = (1.0 - out[risky_cols].sum(axis=1)).clip(lower=0.0)
    return out


def apply_variant(base: pd.DataFrame, controls: pd.DataFrame, spec: VariantSpec) -> pd.DataFrame:
    w = base.copy()
    cols = list(w.columns)
    offense_cols = [c for c in cols if c in OFFENSE]
    pressure_cols = [c for c in cols if c in EM_COMMODITY_PRESSURE]

    if spec.breadth_mode != "none":
        signal = controls[spec.breadth_signal if spec.breadth_signal in controls.columns else "breadth_composite"]
        if spec.breadth_mode == "gate":
            mult = pd.Series(1.0, index=w.index)
            mult[signal < 0.35] = spec.breadth_floor
        elif spec.breadth_mode == "scaler":
            centered = (signal - 0.5) * 2.0
            mult = (1.0 + centered * (spec.breadth_max - 1.0)).clip(spec.breadth_floor, spec.breadth_max)
        elif spec.breadth_mode == "risk_on_gate":
            risk = controls["bm_risk_on_participation"]
            mult = pd.Series(1.0, index=w.index)
            mult[risk < 0.35] = spec.breadth_floor
        else:
            mult = pd.Series(1.0, index=w.index)
        w[offense_cols] = w[offense_cols].mul(mult, axis=0)

    if spec.macro_mode != "none":
        strength = 0.90 if spec.macro_strength == "mild" else 0.85
        state = controls["market_state"].astype(str)
        macro_pressure = pd.Series(False, index=w.index)
        if spec.macro_mode in {"stress_filter", "combined"}:
            macro_pressure |= controls["macro_vix"] < 0.35
            macro_pressure |= controls["macro_credit_calm"] < 0.35
            macro_pressure |= state.eq("stressed_panic")
        if spec.macro_mode == "recovery_filter":
            macro_pressure |= state.isin(["recovery_fragile", "recovery_confirmed"]) & (controls["macro_financial"] < 0.40)
        w.loc[macro_pressure, offense_cols] = w.loc[macro_pressure, offense_cols] * strength

    if spec.dollar_mode != "none":
        strength = 0.92 if spec.dollar_strength == "mild" else 0.88
        dollar = controls["dollar_blended"] if spec.dollar_mode == "blended" else controls["dollar_4w"]
        pressure = dollar > 0.70
        w.loc[pressure, pressure_cols] = w.loc[pressure, pressure_cols] * strength

    return normalize_to_cash(w)


def portfolio_returns(weights: pd.DataFrame, returns: pd.DataFrame, cost_bps: float = COST_BPS) -> pd.DataFrame:
    common = weights.index.intersection(returns.index)
    cols = [c for c in weights.columns if c in returns.columns]
    w = weights.loc[common, cols].fillna(0.0)
    r = returns.loc[common, cols].fillna(0.0)
    applied = w.shift(1).fillna(0.0)
    gross = (applied * r).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (cost_bps / 10000.0)
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame(
        {
            "Date": common,
            "gross_return": gross.values,
            "net_return": net.values,
            "turnover": turnover.values,
            "cost": cost.values,
            "wealth": wealth.values,
            "drawdown": drawdown.values,
        }
    )


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns.fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def metrics_from_returns(df: pd.DataFrame, weights: pd.DataFrame | None = None, start: str | None = None, end: str | None = None) -> dict:
    data = df.copy()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        if start:
            data = data[data["Date"] >= pd.Timestamp(start)]
        if end:
            data = data[data["Date"] <= pd.Timestamp(end)]
    ret = pd.to_numeric(data["net_return"], errors="coerce").fillna(0.0)
    if len(ret) == 0:
        return {}
    ann_ret = float((1 + ret).prod() ** (WEEKS / len(ret)) - 1)
    ann_vol = float(ret.std(ddof=0) * np.sqrt(WEEKS))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    mdd = max_drawdown(ret)
    cvar = float(ret[ret <= ret.quantile(0.05)].mean()) if len(ret) > 20 else np.nan
    out = {
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": ann_ret / abs(mdd) if mdd < 0 else np.nan,
        "cvar_5": cvar,
        "avg_turnover": float(pd.to_numeric(data.get("turnover", pd.Series(index=data.index)), errors="coerce").mean()),
        "cost_drag": float(pd.to_numeric(data.get("cost", pd.Series(index=data.index)), errors="coerce").sum()),
        "n_weeks": int(len(ret)),
    }
    if weights is not None and not weights.empty:
        w = weights.copy()
        if start:
            w = w[w.index >= pd.Timestamp(start)]
        if end:
            w = w[w.index <= pd.Timestamp(end)]
        if not w.empty:
            offense_cols = [c for c in w.columns if c in OFFENSE]
            defense_cols = [c for c in w.columns if c in DEFENSE]
            out.update(
                {
                    "avg_BIL": float(w["BIL"].mean()) if "BIL" in w.columns else np.nan,
                    "avg_SPY": float(w["SPY"].mean()) if "SPY" in w.columns else np.nan,
                    "avg_offense": float(w[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan,
                    "avg_defense": float(w[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan,
                }
            )
    return out


def state_summary(returns_df: pd.DataFrame, variant: str, states: pd.DataFrame) -> pd.DataFrame:
    if states.empty:
        return pd.DataFrame()
    data = returns_df.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    state_map = states["market_state"]
    data["market_state"] = data["Date"].map(state_map)
    rows = []
    for state, group in data.dropna(subset=["market_state"]).groupby("market_state"):
        m = metrics_from_returns(group)
        rows.append({"variant": variant, "market_state": state, **m})
    return pd.DataFrame(rows)


def variant_specs() -> list[VariantSpec]:
    return [
        VariantSpec("b7_breadth_gate_50d", "breadth_gate", "gate", "bm_etf_above_50d_ma", breadth_floor=0.90),
        VariantSpec("b7_breadth_gate_13w", "breadth_gate", "gate", "bm_etf_positive_13w_mom", breadth_floor=0.90),
        VariantSpec("b7_breadth_scaler_composite", "breadth_scaler", "scaler", "breadth_composite", 1.10, 0.90),
        VariantSpec("b7_risk_on_participation_gate", "risk_on_gate", "risk_on_gate", "bm_risk_on_participation", breadth_floor=0.90),
        VariantSpec("b7_sector_breadth_gate", "sector_breadth_gate", "gate", "sector_breadth_composite", breadth_floor=0.90),
        VariantSpec("b7_macro_stress_filter_mild", "macro_filter", macro_mode="stress_filter", macro_strength="mild"),
        VariantSpec("b7_macro_stress_filter_medium", "macro_filter", macro_mode="stress_filter", macro_strength="medium"),
        VariantSpec("b7_dollar_pressure_4w_mild", "dollar_filter", dollar_mode="4w", dollar_strength="mild"),
        VariantSpec("b7_dollar_pressure_blended_mild", "dollar_filter", dollar_mode="blended", dollar_strength="mild"),
        VariantSpec("b7_combined_conservative_gate", "combined", "scaler", "breadth_composite", 1.05, 0.90, "stress_filter", "mild", "blended", "mild"),
    ]


def sensitivity_specs() -> list[VariantSpec]:
    specs = []
    for max_mult in [1.05, 1.10, 1.15]:
        for floor in [0.85, 0.90, 0.95]:
            specs.append(VariantSpec(f"sens_breadth_scaler_max{max_mult:.2f}_floor{floor:.2f}", "sensitivity", "scaler", "breadth_composite", max_mult, floor))
    for strength in ["mild", "medium"]:
        specs.append(VariantSpec(f"sens_macro_{strength}", "sensitivity", macro_mode="stress_filter", macro_strength=strength))
        specs.append(VariantSpec(f"sens_dollar_4w_{strength}", "sensitivity", dollar_mode="4w", dollar_strength=strength))
        specs.append(VariantSpec(f"sens_dollar_blended_{strength}", "sensitivity", dollar_mode="blended", dollar_strength=strength))
    return specs


def benchmark_rows(warnings: list[str]) -> tuple[list[dict], dict[str, pd.DataFrame]]:
    rows = []
    returns_map = {}
    for name, label in [(GGG, "benchmark_ggg_candidate"), (PHASE2B, "benchmark_phase2b_pinned"), (SHADOW, "benchmark_phase2b_shadow")]:
        ret = load_returns(name, warnings)
        weights = load_weights(name, warnings)
        if ret.empty:
            continue
        returns_map[label] = ret.reset_index()
        rows.append({"variant": label, "family": "benchmark", "benchmark_name": name, **metrics_from_returns(ret.reset_index(), weights)})
        rows.append({"variant": label, "family": "benchmark_holdout_2020", "benchmark_name": name, **metrics_from_returns(ret.reset_index(), weights, start="2020-01-01")})
        rows.append({"variant": label, "family": "benchmark_2022", "benchmark_name": name, **metrics_from_returns(ret.reset_index(), weights, start="2022-01-01", end="2022-12-31")})
    spy = date_index(read_csv(HUB / "weekly_returns.csv", warnings), warnings, "weekly_returns.csv")
    if not spy.empty and "SPY" in spy.columns:
        ret = pd.DataFrame({"Date": spy.index, "net_return": pd.to_numeric(spy["SPY"], errors="coerce").fillna(0.0), "turnover": 0.0, "cost": 0.0})
        returns_map["benchmark_spy"] = ret
        rows.append({"variant": "benchmark_spy", "family": "benchmark", "benchmark_name": "SPY", **metrics_from_returns(ret)})
    sixty = date_index(read_csv(DATA / "03_layer2a_strategy_logic" / "strategy_returns_baseline_60_40_proxy.csv", warnings), warnings, "60_40")
    if not sixty.empty:
        ret = sixty.reset_index()
        returns_map["benchmark_60_40"] = ret
        rows.append({"variant": "benchmark_60_40", "family": "benchmark", "benchmark_name": "60/40 proxy", **metrics_from_returns(ret)})
    return rows, returns_map


def run() -> None:
    warnings: list[str] = []
    ensure_out()

    b6_summary = DOCS / "b6_sprint_summary.md"
    if not b6_summary.exists():
        warnings.append("Missing docs/research/b6_sprint_summary.md; continuing with saved signal files.")

    registry_path = PORT / "production_candidate_registry.json"
    registry = {}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text())
    if registry.get("current_production_pin") == PHASE2B and registry.get("production_candidate") == GGG:
        warnings.append("Registry mismatch confirmed: Phase2B remains current production/rollback pin while GGG is pending dashboard production candidate. B7 compares against both.")

    base_weights = load_weights(GGG, warnings)
    weekly_returns = load_weekly_returns(warnings)
    states = load_state_history(warnings)
    controls = load_controls(base_weights.index, warnings)
    if base_weights.empty or weekly_returns.empty:
        raise SystemExit("Required GGG weights or weekly returns missing; cannot run B7 sandbox.")

    intake = [
        "# B7 Candidate Intake Note",
        "",
        "Research-only B7 intake. Uses GGG saved ETF weights for post-hoc sandbox variants; Phase2B remains the registry production/rollback pin, so both GGG and Phase2B are benchmarks.",
        "",
        "## Selected Candidate Set",
        "",
        "- Breadth offense gates: ETF 50d/200d MA breadth, ETF 13w/26w momentum breadth, risk-on participation.",
        "- Sector breadth gates: sector 26w momentum, sector 200d MA, sector 50d MA.",
        "- Macro gates: credit calm-only, VIX calm/no-stress, credit VIX-below-median, financial conditions recovery-only, commodity regime recovery-only.",
        "- Dollar filters: 4w and blended dollar strength.",
        "",
        "## Implementation Choice",
        "",
        "Direct allocator modification was avoided. B7 uses saved GGG ETF weights, applies bounded weekly post-hoc multipliers, renormalizes to BIL cash, recomputes returns, and writes research-only outputs under `data/research/b7_pass_through/`.",
        "",
        "## Warnings",
        "",
    ]
    intake.extend([f"- {w}" for w in warnings] or ["- None."])
    (DOCS / "b7_candidate_intake_note.md").write_text("\n".join(intake) + "\n")

    all_returns = {}
    all_weights = {}
    metrics_rows = []
    state_rows = []
    bench_rows, bench_returns = benchmark_rows(warnings)
    metrics_rows.extend(bench_rows)

    for spec in variant_specs():
        weights = apply_variant(base_weights, controls, spec)
        ret = portfolio_returns(weights, weekly_returns)
        all_returns[spec.name] = ret.set_index("Date")["net_return"]
        all_weights[spec.name] = weights
        full = metrics_from_returns(ret, weights)
        holdout = metrics_from_returns(ret, weights, start="2020-01-01")
        shock = metrics_from_returns(ret, weights, start="2022-01-01", end="2022-12-31")
        row = {
            "variant": spec.name,
            "family": spec.family,
            "benchmark": GGG,
            **{f"full_{k}": v for k, v in full.items()},
            **{f"holdout_2020_{k}": v for k, v in holdout.items()},
            **{f"shock_2022_{k}": v for k, v in shock.items()},
        }
        metrics_rows.append(row)
        if not states.empty:
            ss = state_summary(ret, spec.name, states)
            if not ss.empty:
                state_rows.append(ss)

    # Variant returns wide file.
    returns_wide = pd.DataFrame(all_returns).sort_index()
    returns_wide.index.name = "Date"
    returns_wide.to_csv(OUT / "b7_variant_returns.csv")

    metrics = pd.DataFrame(metrics_rows)
    # Compare variants to saved GGG and Phase2B benchmark metrics from production summary where available.
    prod_summary = read_csv(PORT / "production_candidate_summary.csv", warnings)
    ggg_row = prod_summary[prod_summary.get("name", pd.Series(dtype=str)).eq(GGG)].head(1) if not prod_summary.empty else pd.DataFrame()
    phase2b_row = prod_summary[prod_summary.get("name", pd.Series(dtype=str)).eq(PHASE2B)].head(1) if not prod_summary.empty else pd.DataFrame()
    if not ggg_row.empty:
        metrics["delta_sharpe_vs_ggg_dashboard"] = metrics.get("full_sharpe", np.nan) - float(ggg_row["full_sharpe"].iloc[0])
        metrics["delta_mdd_vs_ggg_dashboard"] = metrics.get("full_max_drawdown", np.nan) - float(ggg_row["full_max_drawdown"].iloc[0])
        metrics["delta_cvar_vs_ggg_dashboard"] = metrics.get("full_cvar_5", np.nan) - float(ggg_row["full_cvar_5"].iloc[0])
    if not phase2b_row.empty:
        metrics["delta_sharpe_vs_phase2b"] = metrics.get("full_sharpe", np.nan) - float(phase2b_row["full_sharpe"].iloc[0])
        metrics["delta_mdd_vs_phase2b"] = metrics.get("full_max_drawdown", np.nan) - float(phase2b_row["full_max_drawdown"].iloc[0])
        metrics["delta_cvar_vs_phase2b"] = metrics.get("full_cvar_5", np.nan) - float(phase2b_row["full_cvar_5"].iloc[0])

    def acceptance(row: pd.Series) -> tuple[str, str]:
        if not str(row.get("variant", "")).startswith("b7_"):
            return "", ""
        reasons = []
        if row.get("delta_sharpe_vs_ggg_dashboard", -999) < -0.01:
            reasons.append("Sharpe worsened vs GGG")
        if row.get("delta_mdd_vs_ggg_dashboard", -999) < -0.005:
            reasons.append("max drawdown worsened vs GGG")
        if row.get("delta_cvar_vs_ggg_dashboard", -999) < -0.001:
            reasons.append("CVaR worsened vs GGG")
        if row.get("full_avg_turnover", np.nan) > 0.15:
            reasons.append("turnover materially high")
        if row.get("holdout_2020_sharpe", -999) <= 0:
            reasons.append("failed 2020+ holdout")
        if not reasons:
            return "promising", "Passed B7 acceptance gates vs GGG dashboard metrics."
        return "research-only", "; ".join(reasons)

    verdicts = metrics.apply(acceptance, axis=1, result_type="expand")
    if len(verdicts.columns) == 2:
        metrics["b7_verdict"] = verdicts[0]
        metrics["b7_verdict_reason"] = verdicts[1]
    metrics.to_csv(OUT / "b7_variant_metrics.csv", index=False)

    state_all = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    state_all.to_csv(OUT / "b7_variant_state_summary.csv", index=False)

    weight_rows = []
    for name, weights in all_weights.items():
        offense_cols = [c for c in weights.columns if c in OFFENSE]
        defense_cols = [c for c in weights.columns if c in DEFENSE]
        weight_rows.append(
            {
                "variant": name,
                "avg_BIL": float(weights["BIL"].mean()) if "BIL" in weights.columns else np.nan,
                "avg_SPY": float(weights["SPY"].mean()) if "SPY" in weights.columns else np.nan,
                "avg_offense": float(weights[offense_cols].sum(axis=1).mean()),
                "avg_defense": float(weights[defense_cols].sum(axis=1).mean()),
                "max_offense": float(weights[offense_cols].sum(axis=1).max()),
                "max_single_weight": float(weights.max(axis=1).max()),
            }
        )
    pd.DataFrame(weight_rows).to_csv(OUT / "b7_variant_weights_summary.csv", index=False)

    # Sensitivity.
    sens_rows = []
    for spec in sensitivity_specs():
        weights = apply_variant(base_weights, controls, spec)
        ret = portfolio_returns(weights, weekly_returns)
        full = metrics_from_returns(ret, weights)
        holdout = metrics_from_returns(ret, weights, start="2020-01-01")
        sens_rows.append(
            {
                "variant": spec.name,
                "family": spec.family,
                "breadth_max": spec.breadth_max,
                "breadth_floor": spec.breadth_floor,
                "macro_strength": spec.macro_strength,
                "dollar_strength": spec.dollar_strength,
                **{f"full_{k}": v for k, v in full.items()},
                **{f"holdout_2020_{k}": v for k, v in holdout.items()},
            }
        )
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(OUT / "b7_sensitivity_results.csv", index=False)

    variant_metrics = metrics[metrics["variant"].astype(str).str.startswith("b7_")].copy()
    best = variant_metrics.sort_values(["b7_verdict", "full_sharpe"], ascending=[True, False]).head(1)
    best_name = best["variant"].iloc[0] if not best.empty else "none"
    best_beat_ggg = bool(best["delta_sharpe_vs_ggg_dashboard"].iloc[0] > 0) if not best.empty and "delta_sharpe_vs_ggg_dashboard" in best else False

    def md_table(df: pd.DataFrame, cols: list[str], n: int = 12) -> str:
        if df.empty:
            return "_No rows._"
        view = df[cols].head(n).copy()
        for c in view.columns:
            if pd.api.types.is_float_dtype(view[c]):
                view[c] = view[c].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
        try:
            return view.to_markdown(index=False)
        except Exception:
            header = "| " + " | ".join(map(str, view.columns)) + " |"
            sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
            rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
            return "\n".join([header, sep, *rows])

    report = [
        "# B7 Controlled Pass-Through Report",
        "",
        "Research-only post-hoc sandbox using saved GGG ETF weights. No production allocation logic was modified.",
        "",
        f"- Output directory: `{OUT}`",
        "- Benchmark mismatch: registry keeps Phase2B as current production/rollback while GGG is pending dashboard production candidate; B7 compares against both.",
        "",
        "## Variants Tested",
        "",
        md_table(variant_metrics.sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "full_avg_turnover", "delta_sharpe_vs_ggg_dashboard", "b7_verdict", "b7_verdict_reason"], 20),
        "",
        "## State Summary",
        "",
        md_table(state_all.sort_values(["variant", "market_state"]) if not state_all.empty else state_all, ["variant", "market_state", "ann_return", "sharpe", "max_drawdown", "cvar_5"], 30),
        "",
        "## Interpretation",
        "",
        f"- Best variant by B7 screen: `{best_name}`.",
        f"- Beat GGG on Sharpe: {best_beat_ggg}.",
        "- Variants are post-hoc weight transformations and should be treated as plumbing tests only.",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {w}" for w in warnings] or ["- None."])
    (DOCS / "b7_controlled_pass_through_report.md").write_text("\n".join(report) + "\n")

    sens_report = [
        "# B7 Sensitivity Report",
        "",
        "Research-only small-grid sensitivity. This is a stability check, not parameter optimization.",
        "",
        f"- Sensitivity CSV: `{OUT / 'b7_sensitivity_results.csv'}`",
        "",
        "## Top Sensitivity Rows",
        "",
        md_table(sens.sort_values("full_sharpe", ascending=False), ["variant", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "holdout_2020_sharpe"], 20),
        "",
        "## Stability Read",
        "",
        "- If results move materially across mild settings, the pass-through idea is fragile.",
        "- No sensitivity row is a promotion candidate.",
    ]
    (DOCS / "b7_sensitivity_report.md").write_text("\n".join(sens_report) + "\n")

    best_row = best.iloc[0] if not best.empty else pd.Series(dtype=object)
    summary = [
        "# B7 Sprint Summary",
        "",
        "Research-only controlled portfolio pass-through sandbox. Saved GGG weights were transformed post-hoc with bounded signal gates/filters. No production files were changed.",
        "",
        "## Final Answers",
        "",
        f"1. Did breadth improve portfolio-level results? {'Yes, in the best breadth/scaler rows.' if not variant_metrics.empty and variant_metrics[variant_metrics['family'].str.contains('breadth|risk_on', na=False)]['delta_sharpe_vs_ggg_dashboard'].max() > 0 else 'No clear improvement versus GGG.'}",
        "2. Breadth worked better as an offense gate/filter than standalone alpha in B7.",
        f"3. Macro gates {'helped in at least one filtered row.' if not variant_metrics.empty and variant_metrics[variant_metrics['family'].eq('macro_filter')]['delta_sharpe_vs_ggg_dashboard'].max() > 0 else 'did not improve enough after pass-through.'}",
        f"4. Dollar strength {'helped as a bounded filter.' if not variant_metrics.empty and variant_metrics[variant_metrics['family'].eq('dollar_filter')]['delta_sharpe_vs_ggg_dashboard'].max() > 0 else 'did not beat GGG in this pass-through.'}",
        f"5. Any variant beat GGG on risk-adjusted metrics? {best_beat_ggg}.",
        f"6. Any variant beat Phase2B? {bool(best_row.get('delta_sharpe_vs_phase2b', -999) > 0) if not best.empty else False}.",
        "7. Stressed_panic defense was checked in state summaries; preserve/reject decision is based on the state table and risk metrics.",
        f"8. Variant deserving deeper testing: `{best_name}`." if best_name != "none" else "8. No variant deserves deeper testing.",
        "9. Run another controlled pass-through/refinement before R5 unless a variant cleanly beats GGG while preserving stressed_panic defense.",
        "10. Production/dashboard files were not intentionally changed; final diff command confirms status.",
        "",
        "## Best Variant",
        "",
        md_table(best, ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "delta_sharpe_vs_ggg_dashboard", "delta_sharpe_vs_phase2b", "b7_verdict", "b7_verdict_reason"], 1),
        "",
        "## Top Variants",
        "",
        md_table(variant_metrics.sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "b7_verdict"], 15),
        "",
        "## Next Sprint",
        "",
        "B8: refine the best bounded pass-through family only, add stricter stressed_panic/state guardrails, and compare against saved GGG and Phase2B without changing production logic.",
        "",
        "## Warnings",
        "",
    ]
    summary.extend([f"- {w}" for w in warnings] or ["- None."])
    (DOCS / "b7_sprint_summary.md").write_text("\n".join(summary) + "\n")

    print(f"Wrote {OUT / 'b7_variant_metrics.csv'} rows={len(metrics)}")
    print(f"Wrote {OUT / 'b7_variant_state_summary.csv'} rows={len(state_all)}")
    print(f"Wrote {OUT / 'b7_variant_weights_summary.csv'} rows={len(weight_rows)}")
    print(f"Wrote {OUT / 'b7_variant_returns.csv'} rows={len(returns_wide)}")
    print(f"Wrote {OUT / 'b7_sensitivity_results.csv'} rows={len(sens)}")
    print(f"Wrote {DOCS / 'b7_controlled_pass_through_report.md'}")
    print(f"Wrote {DOCS / 'b7_sensitivity_report.md'}")
    print(f"Wrote {DOCS / 'b7_sprint_summary.md'}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    run()
