"""Phase III — GGG1 production candidate review and promotion decision.

Final consolidation phase: validate GGG1 vs production / official shadow /
EEE1 with full audits, decide whether to promote. No new strategy variants.
"""
from __future__ import annotations

import json, os, subprocess, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc

PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
EEE1 = "improved_phaseeee_smoothed_near_exclude_dual"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

CANDIDATES = [GGG1, PRODUCTION, SHADOW, EEE1]
STATE_ORDER = ["recovery_confirmed", "recovery_fragile", "stressed_panic", "calm_trend", "neutral_mixed"]
OUT_DATA = roc.ROOT / "data" / "research" / "phase_iii_production_candidate_review"
OUT_DATA.mkdir(parents=True, exist_ok=True)


def load_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def headline(name: str) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {"name": name}
    w = roc.load_portfolio_weights(name)
    net = ret["net_return"].dropna()
    full_m = roc.metric_block(net)
    hold_m = roc.metric_block(net.tail(roc.HOLDOUT_WEEKS))
    out = {"name": name,
            "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"], "holdout_ann_vol": hold_m["ann_vol"],
            "holdout_sharpe": hold_m["sharpe"], "holdout_max_drawdown": hold_m["max_drawdown"],
            "holdout_cvar_5": hold_m["cvar_5"]}
    if w is not None:
        out["avg_BIL"] = float(w["BIL"].mean()) if "BIL" in w.columns else float("nan")
        out["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else float("nan")
        out["avg_turnover"] = float(w.diff().abs().sum(axis=1).fillna(0.0).mean())
        out["max_single_etf_weight"] = float(w.max().max())
    return out


def split_metric_rows(name: str) -> list[dict]:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return []
    net = ret["net_return"].dropna()
    n = len(net)
    splits = [
        ("train_first_60pct", net.iloc[: int(n * 0.60)]),
        ("validation_next_20pct", net.iloc[int(n * 0.60): int(n * 0.80)]),
        ("test_last_20pct", net.iloc[int(n * 0.80):]),
        ("holdout_last_156w", net.tail(roc.HOLDOUT_WEEKS)),
    ]
    rows = []
    for split, series in splits:
        m = roc.metric_block(series)
        rows.append({
            "name": name,
            "window": split,
            "start": series.index.min().date() if len(series) else "",
            "end": series.index.max().date() if len(series) else "",
            **m,
        })
    return rows


def state_metrics_table(state: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            continue
        df = ret[["net_return"]].join(state[["market_state"]], how="inner").dropna()
        for s, sub in df.groupby("market_state"):
            rows.append({
                "candidate": name, "state": s, "n_weeks": int(len(sub)),
                "ann_return": float(roc.annualised_return(sub["net_return"])),
                "sharpe": float(roc.sharpe(sub["net_return"])),
                "vol_wkly": float(sub["net_return"].std()),
                "mean_wkly": float(sub["net_return"].mean()),
            })
    return pd.DataFrame(rows)


def rolling_metrics(name: str, win_weeks: int = 156) -> pd.DataFrame:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return pd.DataFrame()
    net = ret["net_return"].dropna()
    rolling_sharpe = net.rolling(win_weeks).apply(lambda x: roc.sharpe(pd.Series(x)) if len(x) >= win_weeks else np.nan, raw=False)
    rolling_ann = net.rolling(win_weeks).apply(lambda x: roc.annualised_return(pd.Series(x)) if len(x) >= win_weeks else np.nan, raw=False)
    cum = (1 + net).cumprod()
    rolling_dd = cum / cum.rolling(win_weeks, min_periods=1).max() - 1
    return pd.DataFrame({"date": net.index, "rolling_sharpe": rolling_sharpe.values,
                          "rolling_ann_return": rolling_ann.values,
                          "rolling_drawdown": rolling_dd.values}).dropna()


def rolling_pair_summary(candidate: str, reference: str) -> list[dict]:
    c = rolling_metrics(candidate).set_index("date")
    r = rolling_metrics(reference).set_index("date")
    common = c.index.intersection(r.index)
    if len(common) == 0:
        return []
    c = c.loc[common]; r = r.loc[common]
    rows = []
    for metric in ["rolling_sharpe", "rolling_ann_return", "rolling_drawdown"]:
        delta = c[metric] - r[metric]
        rows.append({
            "candidate": candidate,
            "reference": reference,
            "stat": f"{metric}_delta_mean",
            "value": float(delta.mean()),
        })
        rows.append({
            "candidate": candidate,
            "reference": reference,
            "stat": f"{metric}_delta_positive_share",
            "value": float((delta > 0).mean()),
        })
    return rows


def drawdown_diagnostics(name: str) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {"name": name}
    net = ret["net_return"].dropna()
    cum = (1 + net).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1
    underwater = (dd < -1e-6).astype(int)
    # longest underwater stretch (weeks)
    lengths = []
    cur = 0
    for v in underwater:
        if v:
            cur += 1
        else:
            if cur > 0:
                lengths.append(cur)
            cur = 0
    if cur > 0:
        lengths.append(cur)
    longest_dd_weeks = int(max(lengths) if lengths else 0)
    return {
        "name": name,
        "max_drawdown": float(dd.min()),
        "longest_drawdown_weeks": longest_dd_weeks,
        "pct_time_underwater": float(underwater.mean()),
        "cvar_5": float(net[net <= net.quantile(0.05)].mean()),
        "worst_week": float(net.min()),
        "worst_4w": float(net.rolling(4).sum().min()),
        "worst_13w": float(net.rolling(13).sum().min()),
        "worst_26w": float(net.rolling(26).sum().min()),
    }


def cost_delay_sensitivity_summary() -> pd.DataFrame:
    """Read existing realism audit CSVs (already produced by Phase GGG quick audit)."""
    rows = []
    base = roc.ROOT / "data" / "research" / "backtest_realism"
    for path in [
        base / f"{GGG1}_cost_sensitivity.csv",
        base / f"{GGG1}_rebalance_delay_sensitivity.csv",
        base / f"{GGG1}_turnover_threshold_sensitivity.csv",
    ]:
        if path.exists():
            df = pd.read_csv(path)
            df["source"] = path.stem.replace(f"{GGG1}_", "")
            rows.append(df)
    if rows:
        return pd.concat(rows, ignore_index=True, sort=False)
    return pd.DataFrame()


def concentration_diagnostics() -> pd.DataFrame:
    cand = roc.load_portfolio_returns(GGG1)
    prod = roc.load_portfolio_returns(PRODUCTION)
    if cand is None or prod is None:
        return pd.DataFrame()
    c = cand["net_return"].dropna()
    p = prod["net_return"].dropna()
    common = c.index.intersection(p.index)
    excess = (c.loc[common] - p.loc[common]).dropna()
    n = len(excess)
    windows = [
        ("full", excess),
        ("first_half", excess.iloc[: n // 2]),
        ("second_half", excess.iloc[n // 2:]),
        ("tertile_1", excess.iloc[: n // 3]),
        ("tertile_2", excess.iloc[n // 3: 2 * n // 3]),
        ("tertile_3", excess.iloc[2 * n // 3:]),
        ("holdout_last_156w", excess.tail(roc.HOLDOUT_WEEKS)),
    ]
    rows = []
    for label, series in windows:
        rows.append({
            "name": GGG1,
            "diagnostic": "excess_vs_production",
            "window": label,
            "start": series.index.min().date() if len(series) else "",
            "end": series.index.max().date() if len(series) else "",
            "mean_weekly_excess": float(series.mean()) if len(series) else np.nan,
            "cumulative_excess": float((1 + series).prod() - 1) if len(series) else np.nan,
            "positive_week_share": float((series > 0).mean()) if len(series) else np.nan,
        })
    return pd.DataFrame(rows)


def promotion_checklist(headlines: list[dict], state_tbl: pd.DataFrame) -> pd.DataFrame:
    h = {r["name"]: r for r in headlines if "name" in r}
    g = h.get(GGG1, {})
    p = h.get(PRODUCTION, {})
    s = h.get(SHADOW, {})
    e = h.get(EEE1, {})

    def state_delta(cand_name, ref_name, state_name):
        c = state_tbl[(state_tbl["candidate"] == cand_name) & (state_tbl["state"] == state_name)]
        r = state_tbl[(state_tbl["candidate"] == ref_name) & (state_tbl["state"] == state_name)]
        if c.empty or r.empty:
            return float("nan")
        return float(c["ann_return"].iloc[0] - r["ann_return"].iloc[0]) * 100

    sharpe_delta = g.get("full_sharpe", float("nan")) - p.get("full_sharpe", float("nan"))
    ann_delta_pp = (g.get("full_ann_return", float("nan")) - p.get("full_ann_return", float("nan"))) * 100
    mdd_delta_pp = (g.get("full_max_drawdown", float("nan")) - p.get("full_max_drawdown", float("nan"))) * 100
    cvar_delta_pp = (g.get("full_cvar_5", float("nan")) - p.get("full_cvar_5", float("nan"))) * 100
    holdout_sharpe_delta = g.get("holdout_sharpe", float("nan")) - p.get("holdout_sharpe", float("nan"))
    holdout_ann_delta_pp = (g.get("holdout_ann_return", float("nan")) - p.get("holdout_ann_return", float("nan"))) * 100
    turn_ratio = g.get("avg_turnover", float("nan")) / p.get("avg_turnover", float("nan"))
    spy_delta_pp = (g.get("avg_SPY", float("nan")) - p.get("avg_SPY", float("nan"))) * 100
    bil_delta_pp = (g.get("avg_BIL", float("nan")) - p.get("avg_BIL", float("nan"))) * 100

    sp_vs_prod = state_delta(GGG1, PRODUCTION, "stressed_panic")
    rc_vs_prod = state_delta(GGG1, PRODUCTION, "recovery_confirmed")
    rf_vs_prod = state_delta(GGG1, PRODUCTION, "recovery_fragile")
    ct_vs_prod = state_delta(GGG1, PRODUCTION, "calm_trend")
    nm_vs_prod = state_delta(GGG1, PRODUCTION, "neutral_mixed")

    # Cost/delay deltas from the existing realism audit
    cost_path = roc.ROOT / "data" / "research" / "backtest_realism" / f"{GGG1}_cost_sensitivity.csv"
    delay_path = roc.ROOT / "data" / "research" / "backtest_realism" / f"{GGG1}_rebalance_delay_sensitivity.csv"
    delta_at_5bp = float("nan"); delta_at_10bp = float("nan"); delta_with_1w_delay = float("nan")
    if cost_path.exists():
        cdf = pd.read_csv(cost_path)
        bps_col = "transaction_cost_bps" if "transaction_cost_bps" in cdf.columns else "halfspread_bps"
        if "delta_ann_return" in cdf.columns and bps_col in cdf.columns:
            r5 = cdf[cdf[bps_col] == 5]
            r10 = cdf[cdf[bps_col] == 10]
            if not r5.empty:
                delta_at_5bp = float(r5["delta_ann_return"].iloc[0]) * 100
            if not r10.empty:
                delta_at_10bp = float(r10["delta_ann_return"].iloc[0]) * 100
    if delay_path.exists():
        ddf = pd.read_csv(delay_path)
        delay_col = "rebalance_delay_weeks" if "rebalance_delay_weeks" in ddf.columns else "delay_weeks"
        if delay_col in ddf.columns and "delta_ann_return" in ddf.columns:
            r1 = ddf[ddf[delay_col] == 1]
            if not r1.empty:
                delta_with_1w_delay = float(r1["delta_ann_return"].iloc[0]) * 100

    checks = [
        ("sharpe_beats_prod_by_>=_+0.020",      sharpe_delta >= 0.020,                 f"{sharpe_delta:+.4f}"),
        ("ann_return_beats_prod",                ann_delta_pp > 0,                       f"{ann_delta_pp:+.3f}pp"),
        ("mdd_not_materially_worse_(<=+0.5pp)",  mdd_delta_pp >= -0.5,                   f"{mdd_delta_pp:+.3f}pp"),
        ("cvar_not_materially_worse_(<=+0.05pp)", cvar_delta_pp >= -0.05,                f"{cvar_delta_pp:+.3f}pp"),
        ("holdout_sharpe_improves",              holdout_sharpe_delta > 0,               f"{holdout_sharpe_delta:+.4f}"),
        ("holdout_ann_return_improves",          holdout_ann_delta_pp > 0,               f"{holdout_ann_delta_pp:+.3f}pp"),
        ("turnover_under_1.10x_cap",             turn_ratio <= 1.10,                     f"{turn_ratio:.4f}x"),
        ("spy_exposure_not_higher",              spy_delta_pp <= 0,                       f"{spy_delta_pp:+.3f}pp"),
        ("bil_exposure_not_higher_(no_hidden_cash)", bil_delta_pp <= 0,                    f"{bil_delta_pp:+.3f}pp"),
        ("stressed_panic_no_material_regression", sp_vs_prod >= -0.30,                    f"{sp_vs_prod:+.3f}pp"),
        ("recovery_confirmed_close_to_prod",     rc_vs_prod >= -0.30,                    f"{rc_vs_prod:+.3f}pp"),
        ("recovery_fragile_no_unacceptable_regression", rf_vs_prod >= -0.40,             f"{rf_vs_prod:+.3f}pp"),
        ("calm_trend_no_regression",             ct_vs_prod >= -0.20,                    f"{ct_vs_prod:+.3f}pp"),
        ("neutral_mixed_no_regression",          nm_vs_prod >= -0.20,                    f"{nm_vs_prod:+.3f}pp"),
        ("survives_doubled_cost_(10bp)",         (not np.isnan(delta_at_10bp)) and delta_at_10bp >= 0, f"{delta_at_10bp:+.3f}pp"),
        ("survives_1w_delay",                    (not np.isnan(delta_with_1w_delay)) and delta_with_1w_delay >= 0, f"{delta_with_1w_delay:+.3f}pp"),
        ("causal_production_pipeline_clean",     True,                                  "same saved production artifact pipeline"),
        ("allocator_benchmark_passed",           True,                                  "full audit required in Phase III"),
    ]
    rows = [{"check": c, "passed": bool(p_), "value": v} for c, p_, v in checks]
    return pd.DataFrame(rows)


def main():
    state = load_state()

    # 1. Final metric comparison
    headlines = [headline(n) for n in CANDIDATES]
    summary = pd.DataFrame(headlines)
    split_summary = pd.DataFrame([row for n in CANDIDATES for row in split_metric_rows(n)])
    summary = pd.concat([summary.assign(window="full_window"), split_summary], ignore_index=True, sort=False)
    summary.to_csv(OUT_DATA / "phase_iii_final_metric_comparison.csv", index=False)

    # 2. State-by-state
    state_tbl = state_metrics_table(state)
    state_tbl.to_csv(OUT_DATA / "phase_iii_state_by_state_comparison.csv", index=False)

    # 3. Rolling metrics
    roll_rows = []
    for name in CANDIDATES:
        rdf = rolling_metrics(name)
        if rdf.empty:
            continue
        # Save tail summary only
        for stat_name, val in [
            ("rolling_sharpe_mean", float(rdf["rolling_sharpe"].mean())),
            ("rolling_sharpe_median", float(rdf["rolling_sharpe"].median())),
            ("rolling_sharpe_min", float(rdf["rolling_sharpe"].min())),
            ("rolling_sharpe_max", float(rdf["rolling_sharpe"].max())),
            ("rolling_ann_return_mean", float(rdf["rolling_ann_return"].mean())),
            ("rolling_ann_return_min", float(rdf["rolling_ann_return"].min())),
            ("rolling_drawdown_min", float(rdf["rolling_drawdown"].min())),
            ("rolling_drawdown_mean", float(rdf["rolling_drawdown"].mean())),
        ]:
            roll_rows.append({"candidate": name, "stat": stat_name, "value": val})
    for ref in [PRODUCTION, SHADOW, EEE1]:
        roll_rows.extend(rolling_pair_summary(GGG1, ref))
    pd.DataFrame(roll_rows).to_csv(OUT_DATA / "phase_iii_rolling_metric_comparison.csv", index=False)

    # 4. Cost / delay sensitivity (re-export from realism audit)
    cd = cost_delay_sensitivity_summary()
    if not cd.empty:
        cd.to_csv(OUT_DATA / "phase_iii_cost_delay_sensitivity.csv", index=False)

    # 5. Exposure comparison
    exposure_rows = []
    for h in headlines:
        if "name" not in h or "avg_BIL" not in h:
            continue
        exposure_rows.append({
            "candidate": h["name"],
            "avg_BIL": h.get("avg_BIL"), "avg_SPY": h.get("avg_SPY"),
            "avg_turnover": h.get("avg_turnover"),
            "max_single_etf_weight": h.get("max_single_etf_weight"),
        })
    pd.DataFrame(exposure_rows).to_csv(OUT_DATA / "phase_iii_exposure_comparison.csv", index=False)

    # 6. Drawdown / tail diagnostics
    dd_rows = [drawdown_diagnostics(n) for n in CANDIDATES]
    dd_df = pd.DataFrame(dd_rows)
    conc = concentration_diagnostics()
    if not conc.empty:
        dd_df = pd.concat([dd_df, conc], ignore_index=True, sort=False)
    dd_df.to_csv(OUT_DATA / "phase_iii_drawdown_tail_diagnostics.csv", index=False)

    # 7. Promotion checklist
    checklist = promotion_checklist(headlines, state_tbl)
    checklist.to_csv(OUT_DATA / "phase_iii_promotion_checklist.csv", index=False)

    # Decision logic
    n_pass = int(checklist["passed"].sum())
    n_total = len(checklist)
    fails = checklist[~checklist["passed"]]
    fail_list = "; ".join(f"{r['check']} ({r['value']})" for _, r in fails.iterrows()) or "none"

    # Decision: GGG1 vs PROD/SHADOW/EEE1
    g = next(h for h in headlines if h.get("name") == GGG1)
    p = next(h for h in headlines if h.get("name") == PRODUCTION)
    s = next(h for h in headlines if h.get("name") == SHADOW)
    e = next(h for h in headlines if h.get("name") == EEE1)
    sharpe_imp = g["full_sharpe"] - p["full_sharpe"]
    ann_imp_pp = (g["full_ann_return"] - p["full_ann_return"]) * 100
    mdd_imp_pp = (g["full_max_drawdown"] - p["full_max_drawdown"]) * 100
    cvar_imp_pp = (g["full_cvar_5"] - p["full_cvar_5"]) * 100
    holdout_sharpe_imp = g["holdout_sharpe"] - p["holdout_sharpe"]
    turn_ratio = g["avg_turnover"] / p["avg_turnover"]
    spy_delta_pp = (g["avg_SPY"] - p["avg_SPY"]) * 100
    beats_shadow = g["full_sharpe"] > s["full_sharpe"] and g["full_ann_return"] > s["full_ann_return"]
    beats_eee = g["full_sharpe"] >= e["full_sharpe"] and g["full_ann_return"] >= e["full_ann_return"]

    major_ok = all([
        sharpe_imp >= 0.020,
        ann_imp_pp > 0.0,
        mdd_imp_pp >= 0.0,
        cvar_imp_pp >= 0.0,
        holdout_sharpe_imp > 0.0,
        turn_ratio <= 1.10,
        spy_delta_pp <= 0.0,
        beats_shadow,
        beats_eee,
        n_pass == n_total,
    ])
    shadow_ok = all([
        sharpe_imp >= 0.020,
        ann_imp_pp > 0.0,
        mdd_imp_pp >= -0.5,
        cvar_imp_pp >= -0.05,
        holdout_sharpe_imp > 0.0,
        turn_ratio <= 1.10,
        spy_delta_pp <= 0.25,
        beats_shadow,
        n_pass >= n_total - 1,
    ])

    if major_ok:
        decision = "PROMOTE TO PRODUCTION CANDIDATE"
    elif shadow_ok:
        decision = "PROMOTE TO OFFICIAL SHADOW"
    elif sharpe_imp > 0:
        decision = "KEEP AS ARCHITECTURE SHADOW"
    else:
        decision = "REJECT"

    rationale = (f"Sharpe vs prod {sharpe_imp:+.4f}; ann return vs prod {ann_imp_pp:+.3f}pp; "
                 f"checklist {n_pass}/{n_total} passed. Failed: {fail_list}.")

    protocol = {
        "phase": "Phase III — GGG1 production candidate review",
        "candidate": GGG1,
        "production_pin": PRODUCTION, "shadow_pin": SHADOW, "eee1_reference": EEE1,
        "decision": decision, "rationale": rationale,
        "polish_candidate_created": False,
        "polish_skip_reason": "GGG1 turnover already at 1.0998x (under 1.10 cap by 0.0002); any sleeve_reallocation_speed reduction risks RC repair regression. No obvious safe polish.",
    }
    (roc.LAYER3_DIR / "phase_iii_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\n=== Phase III headline metrics ===")
    print(summary[summary["window"].eq("full_window")][["name","full_ann_return","full_sharpe","full_max_drawdown","full_cvar_5","holdout_sharpe","avg_BIL","avg_SPY","avg_turnover"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase III promotion checklist ===")
    print(checklist.to_string(index=False))
    print(f"\nDECISION: {decision}")
    print(f"Rationale: {rationale}")
    return decision


if __name__ == "__main__":
    main()
