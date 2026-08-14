"""R4 ETF pairs / statistical-arbitrage signal lab.

Research-only output. Tests priority ETF pairs for training-period
cointegration, spread stationarity, mean-reversion half-life, IC, state
conditional behavior, and redundancy. It does not create a traded long/short
portfolio and does not modify production allocation artifacts.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HOLDOUT_START,
    HORIZONS,
    SIGNAL_DIR,
    ensure_parent,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
    max_redundancy_against,
    newey_west_tstat,
    robust_z,
)


PRIORITY_PAIRS = [
    ("SPY", "QQQ"),
    ("IWM", "SPY"),
    ("TLT", "SPY"),
    ("GLD", "TLT"),
    ("XLE", "USO"),
    ("HYG", "LQD"),
    ("EEM", "SPY"),
    ("XLK", "QQQ"),
]


def ols_spread(log_a: pd.Series, log_b: pd.Series) -> tuple[float, float, pd.Series]:
    aligned = pd.concat([log_a.rename("a"), log_b.rename("b")], axis=1).dropna()
    if aligned.empty:
        return np.nan, np.nan, pd.Series(dtype=float)
    beta, alpha = np.polyfit(aligned["b"], aligned["a"], 1)
    spread = log_a - (alpha + beta * log_b)
    return float(alpha), float(beta), spread


def ou_half_life(spread: pd.Series) -> float:
    clean = spread.dropna()
    lagged = clean.shift(1)
    delta = clean.diff()
    reg = pd.concat([delta.rename("delta"), lagged.rename("lagged")], axis=1).dropna()
    if len(reg) < 52:
        return np.nan
    beta, alpha = np.polyfit(reg["lagged"], reg["delta"], 1)
    if beta >= 0:
        return math.inf
    return float(-math.log(2) / beta)


def pair_ic(signal: pd.Series, prices: pd.DataFrame, a: str, b: str, horizon: int) -> dict:
    fwd_a = prices[a].shift(-horizon) / prices[a] - 1.0
    fwd_b = prices[b].shift(-horizon) / prices[b] - 1.0
    target = fwd_a - fwd_b
    aligned = pd.concat([signal.rename("signal"), target.rename("target")], axis=1).dropna()
    if len(aligned) < 52 or aligned["signal"].nunique() < 2 or aligned["target"].nunique() < 2:
        return {"mean_ic": np.nan, "ic_tstat_nw": np.nan, "hit_rate": np.nan, "n_obs": len(aligned)}
    # This is a time-series IC for the pair's relative return, not a portfolio return.
    rolling_proxy = aligned["signal"].rolling(52, min_periods=26).corr(aligned["target"])
    single_ic = float(aligned["signal"].corr(aligned["target"], method="spearman"))
    hit_rate = float((np.sign(aligned["signal"]) == np.sign(aligned["target"])).mean())
    return {
        "mean_ic": single_ic,
        "ic_tstat_nw": newey_west_tstat(rolling_proxy.dropna()),
        "hit_rate": hit_rate,
        "n_obs": int(len(aligned)),
    }


def state_pair_ic(signal: pd.Series, prices: pd.DataFrame, states: pd.DataFrame, a: str, b: str, horizon: int) -> pd.DataFrame:
    fwd_a = prices[a].shift(-horizon) / prices[a] - 1.0
    fwd_b = prices[b].shift(-horizon) / prices[b] - 1.0
    target = fwd_a - fwd_b
    state_map = states.set_index("Date")["market_state"] if not states.empty else pd.Series(dtype=object)
    aligned = pd.concat([signal.rename("signal"), target.rename("target")], axis=1).dropna()
    aligned["market_state"] = aligned.index.map(state_map)
    rows = []
    for state, group in aligned.dropna(subset=["market_state"]).groupby("market_state"):
        if len(group) < 20 or group["signal"].nunique() < 2 or group["target"].nunique() < 2:
            ic = np.nan
            tstat = np.nan
            hit = np.nan
            warning = "Small or degenerate state sample."
        else:
            ic = float(group["signal"].corr(group["target"], method="spearman"))
            roll = group["signal"].rolling(26, min_periods=13).corr(group["target"])
            tstat = newey_west_tstat(roll.dropna())
            hit = float((np.sign(group["signal"]) == np.sign(group["target"])).mean())
            warning = "Small state sample; treat as directional only." if len(group) < 30 else ""
        rows.append(
            {
                "market_state": state,
                "horizon_weeks": horizon,
                "state_ic": ic,
                "state_ic_tstat_nw": tstat,
                "state_hit_rate": hit,
                "state_n_obs": int(len(group)),
                "state_warning": warning,
            }
        )
    return pd.DataFrame(rows)


def pair_panel_signal(signal: pd.Series, a: str, b: str, signal_name: str, spread_z: pd.Series) -> pd.DataFrame:
    rows = []
    for ticker, multiplier, leg in [(a, 1.0, "long_if_positive"), (b, -1.0, "short_if_positive")]:
        observed = signal * multiplier
        rows.append(
            pd.DataFrame(
                {
                    "Date": observed.index,
                    "Ticker": ticker,
                    "signal_name": signal_name,
                    "pair": f"{a}/{b}",
                    "leg": leg,
                    "signal_value_observed": observed.values,
                    "signal_value_tradable": observed.shift(1).values,
                    "spread_z_observed": spread_z.values,
                    "source": "weekly_prices.csv training-period hedge ratio",
                    "frequency": "weekly",
                    "lag_periods": 1,
                    "research_only": True,
                    "notes": "Mean-reversion pair signal; diagnostic only, no traded long/short portfolio created.",
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)
    if prices.empty:
        raise SystemExit("weekly_prices.csv is required for R4 ETF pairs lab.")

    statsmodels_available = importlib.util.find_spec("statsmodels") is not None
    if statsmodels_available:
        from statsmodels.tsa.stattools import adfuller, coint
    else:
        adfuller = None
        coint = None
        warnings.append("statsmodels is unavailable; cointegration and ADF tests will be skipped.")

    rows: list[dict] = []
    state_rows_all: list[pd.DataFrame] = []
    for a, b in PRIORITY_PAIRS:
        pair_label = f"{a}/{b}"
        row: dict = {
            "pair": pair_label,
            "ticker_a": a,
            "ticker_b": b,
            "signal_file": "",
            "verdict": "skipped",
            "verdict_reason": "",
        }
        if a not in prices.columns or b not in prices.columns:
            missing = [ticker for ticker in [a, b] if ticker not in prices.columns]
            row["verdict_reason"] = f"Missing ticker(s) in weekly_prices.csv: {missing}"
            rows.append(row)
            continue

        pair_prices = prices[[a, b]].apply(pd.to_numeric, errors="coerce").dropna()
        train = pair_prices[pair_prices.index < HOLDOUT_START]
        row["training_start"] = train.index.min().date().isoformat() if not train.empty else ""
        row["training_end"] = train.index.max().date().isoformat() if not train.empty else ""
        row["train_obs"] = int(len(train))
        if len(train) < 156:
            row["verdict_reason"] = "Fewer than 156 pre-2020 training observations."
            rows.append(row)
            continue

        log_train_a = np.log(train[a])
        log_train_b = np.log(train[b])
        alpha, beta, train_spread = ols_spread(log_train_a, log_train_b)
        row["hedge_alpha_train"] = alpha
        row["hedge_beta_train"] = beta
        if not np.isfinite(beta):
            row["verdict_reason"] = "Training hedge-ratio fit failed."
            rows.append(row)
            continue

        if statsmodels_available:
            try:
                row["cointegration_pvalue_train"] = float(coint(log_train_a, log_train_b)[1])
            except Exception as exc:
                row["cointegration_pvalue_train"] = np.nan
                warnings.append(f"{pair_label}: cointegration test failed: {exc}")
            try:
                row["adf_pvalue_train_spread"] = float(adfuller(train_spread.dropna(), autolag="AIC")[1])
            except Exception as exc:
                row["adf_pvalue_train_spread"] = np.nan
                warnings.append(f"{pair_label}: ADF test failed: {exc}")
        else:
            row["cointegration_pvalue_train"] = np.nan
            row["adf_pvalue_train_spread"] = np.nan

        row["ou_half_life_weeks_train"] = ou_half_life(train_spread)
        log_a = np.log(prices[a])
        log_b = np.log(prices[b])
        spread = log_a - (alpha + beta * log_b)
        spread_z = robust_z(spread, 52, 26)
        pair_signal_observed = -spread_z
        pair_signal_tradable = pair_signal_observed.shift(1)

        full_ics = []
        holdout_ics = []
        min_n = 10**9
        min_holdout = 10**9
        for horizon in HORIZONS:
            metrics = pair_ic(pair_signal_tradable, prices, a, b, horizon)
            row[f"full_ic_{horizon}w"] = metrics["mean_ic"]
            row[f"full_ic_tstat_nw_{horizon}w"] = metrics["ic_tstat_nw"]
            row[f"full_hit_rate_{horizon}w"] = metrics["hit_rate"]
            row[f"full_n_obs_{horizon}w"] = metrics["n_obs"]
            aligned = pd.concat(
                [
                    pair_signal_tradable.rename("signal"),
                    (prices[a].shift(-horizon) / prices[a] - 1.0 - (prices[b].shift(-horizon) / prices[b] - 1.0)).rename("target"),
                ],
                axis=1,
            ).dropna()
            hold = aligned[aligned.index >= HOLDOUT_START]
            hold_ic = float(hold["signal"].corr(hold["target"], method="spearman")) if len(hold) >= 52 and hold["signal"].nunique() > 1 and hold["target"].nunique() > 1 else np.nan
            row[f"holdout_ic_{horizon}w"] = hold_ic
            row[f"holdout_n_obs_{horizon}w"] = int(len(hold))
            if pd.notna(metrics["mean_ic"]):
                full_ics.append(metrics["mean_ic"])
            if pd.notna(hold_ic):
                holdout_ics.append(hold_ic)
            min_n = min(min_n, metrics["n_obs"])
            min_holdout = min(min_holdout, len(hold))
            state = state_pair_ic(pair_signal_tradable, prices, states, a, b, horizon)
            if not state.empty:
                state["pair"] = pair_label
                state_rows_all.append(state)

        row["avg_full_ic"] = float(np.mean(full_ics)) if full_ics else np.nan
        row["avg_holdout_ic"] = float(np.mean(holdout_ics)) if holdout_ics else np.nan
        row["min_full_n_obs"] = int(min_n if min_n != 10**9 else 0)
        row["min_holdout_n_obs"] = int(min_holdout if min_holdout != 10**9 else 0)

        signal_name = f"r4_pair_{a.lower()}_{b.lower()}"
        panel = pair_panel_signal(pair_signal_observed, a, b, signal_name, spread_z)
        max_red, red_name = max_redundancy_against(panel[["Date", "Ticker", "signal_name", "signal_value_tradable"]], strong_panels, min_obs=50)
        row["max_redundancy_vs_strong"] = max_red
        row["most_redundant_existing_signal"] = red_name

        coint_ok = pd.notna(row["cointegration_pvalue_train"]) and row["cointegration_pvalue_train"] <= 0.05
        adf_ok = pd.notna(row["adf_pvalue_train_spread"]) and row["adf_pvalue_train_spread"] <= 0.05
        half_life = row["ou_half_life_weeks_train"]
        half_life_ok = pd.notna(half_life) and np.isfinite(half_life) and 2 <= half_life <= 13
        obs_ok = row["min_full_n_obs"] >= 156 and row["min_holdout_n_obs"] >= 52
        ic_ok = pd.notna(row["avg_full_ic"]) and row["avg_full_ic"] > 0 and pd.notna(row["avg_holdout_ic"]) and row["avg_holdout_ic"] > 0
        red_ok = pd.isna(max_red) or max_red <= 0.50
        statistically_viable = coint_ok and adf_ok and pd.notna(half_life) and np.isfinite(half_life) and 1 <= half_life <= 52

        reasons = []
        if not coint_ok:
            reasons.append("failed training-period cointegration p<=0.05")
        if not adf_ok:
            reasons.append("failed training-spread ADF p<=0.05")
        if not half_life_ok:
            reasons.append("OU half-life not in 2-13 week range")
        if not obs_ok:
            reasons.append("insufficient IC observations")
        if not ic_ok:
            reasons.append("weak or non-positive full/holdout pair IC")
        if not red_ok:
            reasons.append("redundancy above 0.50 versus existing strong signals")

        if not reasons:
            row["verdict"] = "candidate-pass"
            row["verdict_reason"] = "Passes cointegration, ADF, half-life, IC, observation, and redundancy gates."
        elif statistically_viable and obs_ok:
            row["verdict"] = "research-only"
            row["verdict_reason"] = "; ".join(reasons)
        else:
            row["verdict"] = "rejected"
            row["verdict_reason"] = "; ".join(reasons)

        if statistically_viable:
            signal_path = SIGNAL_DIR / f"signal_{signal_name}.csv"
            ensure_parent(signal_path)
            panel.to_csv(signal_path, index=False)
            row["signal_file"] = str(signal_path)
        rows.append(row)

    report_df = pd.DataFrame(rows)
    out = SIGNAL_DIR / "etf_pairs_cointegration_report.csv"
    ensure_parent(out)
    report_df.to_csv(out, index=False)

    state_df = pd.concat(state_rows_all, ignore_index=True) if state_rows_all else pd.DataFrame()
    candidate_pass = report_df[report_df["verdict"].eq("candidate-pass")]
    research_only = report_df[report_df["verdict"].eq("research-only")]
    rejected = report_df[report_df["verdict"].eq("rejected")]
    skipped = report_df[report_df["verdict"].eq("skipped")]

    report_path = DOCS_RESEARCH_DIR / "etf_pairs_signal_report.md"
    report = [
        "# R4 ETF Pairs Signal Report",
        "",
        "Research-only ETF pairs/statistical-arbitrage lab. Cointegration, ADF, hedge ratio, and OU half-life are estimated on pre-2020 training data where possible. No traded long/short portfolio was created.",
        "",
        f"- Output CSV: `{out}`",
        f"- Priority pairs tested: {len(report_df)}",
        f"- Candidate-pass: {len(candidate_pass)}",
        f"- Research-only: {len(research_only)}",
        f"- Rejected: {len(rejected)}",
        f"- Skipped: {len(skipped)}",
        "",
        "## Pair verdicts",
        "",
        markdown_table(
            report_df[
                [
                    "pair",
                    "verdict",
                    "cointegration_pvalue_train",
                    "adf_pvalue_train_spread",
                    "ou_half_life_weeks_train",
                    "avg_full_ic",
                    "avg_holdout_ic",
                    "max_redundancy_vs_strong",
                    "verdict_reason",
                ]
            ]
        ),
        "",
        "## Viability at weekly frequency",
        "",
    ]
    if candidate_pass.empty:
        report.append("No priority ETF pair cleared the full weekly-frequency candidate-pass gate. Pairs may still be useful diagnostics, but the evidence is not strong enough for a new production signal family.")
    else:
        report.append("At least one ETF pair cleared the research pass gate; these remain research-only until a separate portfolio integration sprint.")
    report.extend(
        [
            "",
            "## Candidate-pass pairs",
            "",
            markdown_table(candidate_pass[["pair", "avg_full_ic", "avg_holdout_ic", "signal_file"]]),
            "",
            "## Research-only pairs",
            "",
            markdown_table(research_only[["pair", "avg_full_ic", "avg_holdout_ic", "verdict_reason", "signal_file"]]),
            "",
            "## Rejected pairs",
            "",
            markdown_table(rejected[["pair", "verdict_reason"]]),
            "",
            "## Skipped pairs",
            "",
            markdown_table(skipped[["pair", "verdict_reason"]]),
            "",
            "## State-conditional pair IC",
            "",
        ]
    )
    if state_df.empty:
        report.append("- State-conditional pair IC unavailable.")
    else:
        report.append(markdown_table(state_df.sort_values("state_ic", ascending=False), max_rows=20))
        report.append("")
        report.append("Worst stressed_panic pair rows:")
        report.append("")
        stress_bad = state_df[state_df["market_state"].eq("stressed_panic")].sort_values("state_ic")
        report.append(markdown_table(stress_bad, max_rows=10))
    report.extend(
        [
            "",
            "## Warnings and limitations",
            "",
        ]
    )
    report.extend([f"- {w}" for w in sorted(set(warnings))] or ["- None."])
    report.extend(
        [
            "",
            "## Research-only confirmation",
            "",
            "R4 wrote pair diagnostics and any statistically viable pair signal CSVs only. It did not create a traded long/short portfolio, change production pins, modify dashboard/public files, or alter live trading/execution logic.",
        ]
    )
    ensure_parent(report_path)
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out}")
    print(f"Wrote {report_path}")
    viable_files = [p for p in report_df.get("signal_file", pd.Series(dtype=str)).dropna().astype(str) if p]
    if viable_files:
        print("Wrote viable pair signal files:")
        for path in viable_files:
            print(f"- {path}")


if __name__ == "__main__":
    main()
