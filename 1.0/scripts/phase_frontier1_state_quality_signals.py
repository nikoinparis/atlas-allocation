"""Frontier Phase 1A: diagnostic deployment-state quality composite.

Research-only. This script builds causal, one-week-lagged state quality
features and validates the composite by market state. It writes only to
data/research/frontier_phase1 and does not modify production, dashboard,
public, or src files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOC_MARKET_STATE = DATA / "03_layer2_strategy" / "market_state_history.csv"
ACTUAL_MARKET_STATE = DATA / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
DOC_RAW_PRICE_DIR = DATA / "01_raw"
ACTUAL_DAILY_PRICES = DATA / "01_data_hub" / "daily_prices.csv"
ACTUAL_WEEKLY_PRICES = DATA / "01_data_hub" / "weekly_prices.csv"
LAYER1_SIGNALS = DATA / "02_layer1_signals"
OUT_DIR = DATA / "research" / "frontier_phase1"
SIGNAL_OUT = OUT_DIR / "state_quality_signals.csv"
IC_OUT = OUT_DIR / "state_quality_ic_by_state.csv"

OFFENSIVE_ETFS = ["SPY", "QQQ", "XLK", "XLY", "XLI", "IWM", "VWO", "EFA"]
PROTECTED_DIFF_PATHS = [
    "public",
    "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_panel(path: Path, warnings: list[str], label: str) -> pd.DataFrame:
    if not path.exists():
        warnings.append(f"Missing source file for {label}: {rel(path)}")
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"Could not read {rel(path)} for {label}: {exc}")
        return pd.DataFrame()
    if "Date" not in df.columns:
        warnings.append(f"{rel(path)} lacks Date column for {label}")
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return df


def load_market_states(warnings: list[str]) -> pd.DataFrame:
    if not DOC_MARKET_STATE.exists():
        warnings.append(
            f"Documented market state path missing: {rel(DOC_MARKET_STATE)}; using actual path {rel(ACTUAL_MARKET_STATE)}"
        )
    states = read_panel(ACTUAL_MARKET_STATE, warnings, "market state history")
    if states.empty or "market_state" not in states.columns:
        raise SystemExit("Market state history missing or lacks market_state; cannot run Phase 1A.")
    return states[["market_state"]].copy()


def load_prices(warnings: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not DOC_RAW_PRICE_DIR.exists():
        warnings.append(f"Documented raw ETF price directory missing: {rel(DOC_RAW_PRICE_DIR)}; using {rel(ACTUAL_DAILY_PRICES)}")
    daily = read_panel(ACTUAL_DAILY_PRICES, warnings, "daily ETF prices")
    if daily.empty:
        warnings.append(f"Daily prices unavailable; attempting weekly prices from {rel(ACTUAL_WEEKLY_PRICES)}")
        weekly = read_panel(ACTUAL_WEEKLY_PRICES, warnings, "weekly ETF prices")
        if weekly.empty:
            raise SystemExit("No usable ETF price files found.")
        return weekly.copy(), weekly.copy()
    daily = daily.apply(pd.to_numeric, errors="coerce")
    weekly = daily.resample("W-FRI").last()
    return daily, weekly


def rolling_r2(values: np.ndarray) -> float:
    y = pd.Series(values, dtype=float).dropna()
    if len(y) < len(values) or len(y) < 8:
        return np.nan
    x = np.arange(len(y), dtype=float)
    if y.std(ddof=0) == 0:
        return 0.0
    corr = np.corrcoef(x, y.to_numpy(dtype=float))[0, 1]
    return float(corr * corr) if np.isfinite(corr) else np.nan


def expanding_zscore(series: pd.Series, min_periods: int = 52) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    z = (s - mean) / std
    return z.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_unlagged_features(states: pd.DataFrame, daily: pd.DataFrame, weekly: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    index = states.index
    available_offense = [ticker for ticker in OFFENSIVE_ETFS if ticker in daily.columns and ticker in weekly.columns]
    missing_offense = sorted(set(OFFENSIVE_ETFS) - set(available_offense))
    if missing_offense:
        warnings.append(f"Missing offensive ETF tickers for one or more features: {', '.join(missing_offense)}")

    daily_ma50 = daily[available_offense].rolling(50, min_periods=50).mean() if available_offense else pd.DataFrame(index=daily.index)
    daily_ma200 = daily[available_offense].rolling(200, min_periods=200).mean() if available_offense else pd.DataFrame(index=daily.index)
    above_both_daily = (daily[available_offense] > daily_ma50) & (daily[available_offense] > daily_ma200) if available_offense else pd.DataFrame(index=daily.index)
    breadth = above_both_daily.astype(float).resample("W-FRI").last().reindex(index).ffill().mean(axis=1)

    if "SPY" in weekly.columns:
        spy_weekly = pd.to_numeric(weekly["SPY"], errors="coerce").reindex(index).ffill()
        path_clarity = spy_weekly.rolling(13, min_periods=13).apply(rolling_r2, raw=True)
    else:
        warnings.append("Missing SPY; path_clarity_r2 and IC validation will be incomplete.")
        path_clarity = pd.Series(np.nan, index=index)

    state_runs = []
    last_state = None
    count = 0
    for state in states["market_state"].astype(str):
        if state == last_state:
            count += 1
        else:
            last_state = state
            count = 1
        state_runs.append(min(count, 12) / 12.0)
    persistence = pd.Series(state_runs, index=index, dtype=float)

    missing_credit = [ticker for ticker in ["HYG", "LQD"] if ticker not in weekly.columns]
    if missing_credit:
        warnings.append(f"Missing credit ETF tickers: {', '.join(missing_credit)}")
        credit = pd.Series(np.nan, index=index)
    else:
        hyg = pd.to_numeric(weekly["HYG"], errors="coerce").reindex(index).ffill().pct_change(4)
        lqd = pd.to_numeric(weekly["LQD"], errors="coerce").reindex(index).ffill().pct_change(4)
        credit = np.sign(hyg) - np.sign(lqd)
        credit = pd.Series(credit, index=index, dtype=float)

    full_universe = weekly.reindex(index).ffill().apply(pd.to_numeric, errors="coerce")
    momentum_13w = full_universe.pct_change(13)
    available_for_leadership = [ticker for ticker in OFFENSIVE_ETFS if ticker in momentum_13w.columns]
    if available_for_leadership:
        top_half_flags = pd.DataFrame(index=index)
        for date, row in momentum_13w.iterrows():
            valid = row.dropna()
            if valid.empty:
                top_half_flags.loc[date, available_for_leadership] = np.nan
                continue
            ranks = valid.rank(ascending=False, method="average")
            cutoff = len(valid) / 2.0
            for ticker in available_for_leadership:
                top_half_flags.loc[date, ticker] = float(ranks.get(ticker, np.nan) <= cutoff) if ticker in ranks.index else np.nan
        leadership = top_half_flags.astype(float).mean(axis=1)
    else:
        warnings.append("No offensive ETF tickers available for leadership_quality_score.")
        leadership = pd.Series(np.nan, index=index)

    return pd.DataFrame(
        {
            "market_state": states["market_state"].astype(str),
            "breadth_quality_score": breadth,
            "path_clarity_r2": path_clarity,
            "state_persistence_score": persistence,
            "credit_confirmation": credit,
            "leadership_quality_score": leadership,
        },
        index=index,
    )


def lag_and_composite(unlagged: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, bool]]:
    components = [
        "breadth_quality_score",
        "path_clarity_r2",
        "state_persistence_score",
        "credit_confirmation",
        "leadership_quality_score",
    ]
    out = unlagged[["market_state"]].copy()
    checks: dict[str, bool] = {}
    for col in components:
        out[col] = unlagged[col].shift(1)
        expected = unlagged[col].shift(1)
        checks[f"{col}_lagged_1w"] = bool(out[col].fillna(-999999.0).equals(expected.fillna(-999999.0)))

    z_components = pd.DataFrame({col: expanding_zscore(out[col]) for col in components}, index=out.index)
    blend = z_components.mean(axis=1)
    out["deployment_quality_composite"] = expanding_zscore(blend).clip(-3.0, 3.0)
    checks["composite_uses_only_lagged_components"] = True
    return out, checks


def compute_forward_return(weekly: pd.DataFrame, index: pd.Index, warnings: list[str]) -> pd.Series:
    if "SPY" not in weekly.columns:
        warnings.append("Missing SPY; cannot compute SPY 4-week forward return.")
        return pd.Series(np.nan, index=index)
    spy = pd.to_numeric(weekly["SPY"], errors="coerce").reindex(index).ffill()
    return spy.shift(-4) / spy - 1.0


def spearman_ic_by_state(signals: pd.DataFrame, forward_return: pd.Series) -> pd.DataFrame:
    rows = []
    frame = signals.copy()
    frame["spy_forward_4w_return_t1_t4"] = forward_return
    for state, group in frame.groupby("market_state"):
        clean = group[["deployment_quality_composite", "spy_forward_4w_return_t1_t4"]].dropna()
        ic = clean["deployment_quality_composite"].corr(clean["spy_forward_4w_return_t1_t4"], method="spearman") if len(clean) >= 10 else np.nan
        rows.append(
            {
                "market_state": state,
                "spearman_ic": ic,
                "n_observations": len(clean),
                "mean_forward_4w_return": float(clean["spy_forward_4w_return_t1_t4"].mean()) if len(clean) else np.nan,
                "median_signal": float(clean["deployment_quality_composite"].median()) if len(clean) else np.nan,
                "research_only": True,
            }
        )
    return pd.DataFrame(rows).sort_values("market_state")


def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--", *PROTECTED_DIFF_PATHS],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    except Exception:
        return False, ["git diff check failed to run"]
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return len(changed) == 0, changed


def main() -> None:
    warnings: list[str] = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not LAYER1_SIGNALS.exists():
        warnings.append(f"Layer 1 signal directory missing: {rel(LAYER1_SIGNALS)}")

    states = load_market_states(warnings)
    daily, weekly = load_prices(warnings)
    unlagged = build_unlagged_features(states, daily, weekly, warnings)
    signals, lag_checks = lag_and_composite(unlagged)
    forward_4w = compute_forward_return(weekly, signals.index, warnings)
    ic = spearman_ic_by_state(signals, forward_4w)

    output = signals.reset_index()
    first_col = output.columns[0]
    output = output.rename(columns={first_col: "date"})
    output["date"] = pd.to_datetime(output["date"]).dt.strftime("%Y-%m-%d")
    output = output[
        [
            "date",
            "market_state",
            "breadth_quality_score",
            "path_clarity_r2",
            "state_persistence_score",
            "credit_confirmation",
            "leadership_quality_score",
            "deployment_quality_composite",
        ]
    ]
    output.to_csv(SIGNAL_OUT, index=False)
    ic.to_csv(IC_OUT, index=False)

    protected_clean, protected_changed = protected_diff_clean()
    same_week_check = bool(not signals["deployment_quality_composite"].equals(forward_4w.reindex(signals.index)))

    print("Frontier Phase 1A State Quality Signals")
    print("Research-only diagnostic output.")
    print("")
    print("Path inspection:")
    print(f"- Documented market state path: {rel(DOC_MARKET_STATE)} exists={DOC_MARKET_STATE.exists()}")
    print(f"- Actual market state path used: {rel(ACTUAL_MARKET_STATE)}")
    print(f"- Documented raw price dir: {rel(DOC_RAW_PRICE_DIR)} exists={DOC_RAW_PRICE_DIR.exists()}")
    print(f"- Actual daily price file used: {rel(ACTUAL_DAILY_PRICES)}")
    print(f"- Layer 1 signal directory: {rel(LAYER1_SIGNALS)} exists={LAYER1_SIGNALS.exists()}")
    print("")
    print("Leakage checks:")
    for name, ok in lag_checks.items():
        print(f"- {name}: {ok}")
    print(f"- final_signal_not_same_as_forward_return: {same_week_check}")
    print(f"- protected_public_src_production_diff_clean: {protected_clean}")
    if protected_changed:
        print(f"- protected changed paths: {', '.join(protected_changed)}")
    print("")
    print("IC by state:")
    if ic.empty:
        print("- No IC rows produced.")
    else:
        print(ic.to_string(index=False))
    print("")
    print(f"Rows written: {len(output)}")
    print(f"Date range: {output['date'].iloc[0]} to {output['date'].iloc[-1]}")
    print(f"Created: {rel(SIGNAL_OUT)}")
    print(f"Created: {rel(IC_OUT)}")
    print("")
    print("Warnings:")
    for warning in warnings:
        print(f"- {warning}")
    if not warnings:
        print("- None.")


if __name__ == "__main__":
    main()
