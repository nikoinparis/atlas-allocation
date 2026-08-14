"""
Macro-Conditioned ETF Tilt Test — Step 2 Sandbox
=================================================
Uses V3 macro regime classifier to test small conservative ETF tilts
inside neutral_mixed weeks only. Research sprint only — no production changes.

Production pin: improved_frontier_phase5_fragility_guard
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "outputs" / "experiment_results" / "macro_conditioned_etf_tilts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_HUB = ROOT / "data" / "01_data_hub"
LAYER2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3 = ROOT / "data" / "05_layer3_portfolio_construction"
V3_DIR = ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v3"

PIN = "improved_frontier_phase5_fragility_guard"
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
COST_PER_TURNOVER = 0.001  # 10 bps per unit turnover (one-way)
MAX_POSITION_CAP = 0.55    # observed BIL max ~0.71 but keep conservative
MIN_OBS_TILT = 30          # minimum observations to drive a tilt rule

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def sharpe(r: pd.Series, periods: int = 52) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5 or r.std() < 1e-12:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(periods))


def sortino(r: pd.Series, periods: int = 52) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5:
        return np.nan
    downside = r[r < 0].std()
    if downside < 1e-12:
        return np.nan
    return float(r.mean() / downside * np.sqrt(periods))


def cvar(r: pd.Series, alpha: float = 0.05) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5:
        return np.nan
    cutoff = np.percentile(r, alpha * 100)
    tail = r[r <= cutoff]
    return float(tail.mean()) if len(tail) > 0 else np.nan


def max_drawdown(r: pd.Series) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 2:
        return np.nan
    wealth = (1 + r).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def calmar(r: pd.Series, periods: int = 52) -> float:
    mdd = max_drawdown(r)
    if mdd >= 0 or np.isnan(mdd):
        return np.nan
    ann_ret = float(r.mean() * periods)
    return ann_ret / abs(mdd)


def hit_rate(r: pd.Series) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5:
        return np.nan
    return float((r > 0).mean())


def full_metrics(r: pd.Series, turnover: pd.Series | None = None, label: str = "") -> dict:
    r = pd.Series(r, dtype=float)
    ann_ret = float(r.mean() * 52)
    ann_vol = float(r.std() * np.sqrt(52))
    wealth = (1 + r.fillna(0)).cumprod()
    dd_series = wealth / wealth.cummax() - 1
    avg_dd = float(dd_series.mean())
    d = {
        "label": label,
        "ann_return": round(ann_ret, 6),
        "ann_vol": round(ann_vol, 6),
        "sharpe": round(sharpe(r), 6),
        "sortino": round(sortino(r), 6),
        "calmar": round(calmar(r), 6),
        "max_drawdown": round(max_drawdown(r), 6),
        "avg_drawdown": round(avg_dd, 6),
        "cvar_5pct": round(cvar(r), 6),
        "hit_rate": round(hit_rate(r), 6),
        "n_weeks": int(r.notna().sum()),
    }
    if turnover is not None:
        d["avg_turnover"] = round(float(turnover.mean()), 6)
        d["ann_turnover"] = round(float(turnover.mean() * 52), 6)
        d["ann_cost_drag"] = round(float(turnover.mean() * COST_PER_TURNOVER * 52), 6)
    return d


def state_metrics(r: pd.Series, state_series: pd.Series, turnover: pd.Series | None = None) -> list[dict]:
    rows = []
    for st in sorted(state_series.dropna().unique()):
        mask = state_series == st
        sub = r[mask].dropna()
        to_sub = turnover[mask] if turnover is not None else None
        d = full_metrics(sub, to_sub, label=str(st))
        d["state"] = str(st)
        rows.append(d)
    return rows


# ---------------------------------------------------------------------------
# [1] Load baseline data
# ---------------------------------------------------------------------------

def load_data() -> dict:
    print("[1] Loading baseline data...")
    prices = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    baseline_rets = pd.read_csv(
        LAYER3 / f"portfolio_version_returns_{PIN}.csv", index_col=0, parse_dates=True
    )
    baseline_wts = pd.read_csv(
        LAYER3 / f"portfolio_version_weights_{PIN}.csv", index_col=0, parse_dates=True
    )
    market_state = pd.read_csv(
        LAYER2B / "market_state_history.csv", index_col=0, parse_dates=True
    )["market_state"]
    v3 = pd.read_csv(V3_DIR / "macro_states_weekly_v3.csv", index_col=0, parse_dates=True)

    # Confirmation features (causal — computed with shift to avoid lookahead)
    hyg = prices["HYG"]
    lqd = prices["LQD"]
    hyg_lqd = hyg / lqd
    credit_trend_improving = (hyg_lqd.pct_change(4) > 0).shift(1)  # 1-week causal lag

    spy_ma40 = prices["SPY"].rolling(40).mean()
    spy_above_200 = (prices["SPY"] > spy_ma40).shift(1)  # causal lag

    etf_rets = prices.pct_change()

    print(f"  Prices: {prices.shape} | Baseline weights: {baseline_wts.shape}")
    print(f"  Market states: {market_state.value_counts().to_dict()}")
    print(f"  V3 macro state dist: {v3['macro_state'].value_counts().to_dict()}")

    return {
        "prices": prices,
        "etf_rets": etf_rets,
        "baseline_rets": baseline_rets,
        "baseline_wts": baseline_wts,
        "market_state": market_state,
        "v3": v3,
        "credit_trend_improving": credit_trend_improving,
        "spy_above_200": spy_above_200,
    }


# ---------------------------------------------------------------------------
# [2] Asset-level forward return diagnostics
# ---------------------------------------------------------------------------

def build_asset_diagnostics(data: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("\n[2] Building asset-level forward return diagnostics...")
    prices = data["prices"]
    market_state = data["market_state"]
    v3 = data["v3"]

    etfs = list(prices.columns)
    # 4-week forward returns (lagged correctly — future returns, aligned by date)
    fwd4 = {}
    for etf in etfs:
        p = prices[etf].dropna()
        f = p.pct_change(4).shift(-4)
        fwd4[etf] = f
    fwd_df = pd.DataFrame(fwd4)

    def etf_stats(dates, label: str) -> list[dict]:
        sub = fwd_df.loc[fwd_df.index.isin(dates)].dropna(how="all")
        rows = []
        for etf in etfs:
            s = sub[etf].dropna()
            if len(s) < 5:
                continue
            rows.append({
                "label": label,
                "etf": etf,
                "n": len(s),
                "mean_4w": round(float(s.mean()), 6),
                "median_4w": round(float(s.median()), 6),
                "sharpe_4w": round(sharpe(s * np.sqrt(13)), 6),  # annualized from 4w
                "hit_rate": round(float((s > 0).mean()), 4),
            })
        return rows

    all_rows = []
    dev_mask = market_state.index <= DEV_END
    holdout_mask = market_state.index >= HOLDOUT_START

    # All macro states × dev/holdout
    for ms in ["expansion", "slowdown", "stress", "overheating"]:
        for period, pmask in [("dev", dev_mask), ("holdout", holdout_mask)]:
            dates = market_state[(market_state.isin(["neutral_mixed", "calm_trend", "stressed_panic",
                                                      "recovery_fragile", "recovery_confirmed"]))
                                 & pmask].index
            v3_dates = v3.loc[v3.index.isin(dates) & (v3["macro_state"] == ms)].index
            all_rows.extend(etf_stats(v3_dates, f"all_mkt|macro_{ms}|{period}"))

            # Neutral_mixed only
            nm_dates = market_state[(market_state == "neutral_mixed") & pmask].index
            nm_v3_dates = v3.loc[v3.index.isin(nm_dates) & (v3["macro_state"] == ms)].index
            all_rows.extend(etf_stats(nm_v3_dates, f"neutral_mixed|macro_{ms}|{period}"))

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(OUT_DIR / "asset_forward_returns_by_macro_state.csv", index=False)
    print(f"  Saved: asset_forward_returns_by_macro_state.csv ({len(df_all)} rows)")

    # Neutral_mixed only (full table, easier to read)
    nm_rows = [r for r in all_rows if r["label"].startswith("neutral_mixed")]
    df_nm = pd.DataFrame(nm_rows)
    df_nm.to_csv(OUT_DIR / "neutral_mixed_asset_forward_returns.csv", index=False)
    print(f"  Saved: neutral_mixed_asset_forward_returns.csv ({len(df_nm)} rows)")

    return df_all, df_nm


# ---------------------------------------------------------------------------
# [3] Derive data-driven tilt buckets from dev period
# ---------------------------------------------------------------------------

def derive_tilt_buckets(df_nm: pd.DataFrame) -> dict:
    """Derive favored ETFs per macro state inside neutral_mixed from dev data only."""
    print("\n[3] Deriving data-driven tilt buckets...")

    buckets = {}
    intuitive_buckets = {
        "expansion":   {"risk_on": ["SPY", "QQQ", "IWM", "HYG", "EFA", "VWO"],
                        "defensive": ["BIL", "IEF", "TLT", "LQD", "GLD"]},
        "slowdown":    {"risk_on": ["SPY", "QQQ", "IWM", "HYG", "EFA", "VWO"],
                        "defensive": ["IEF", "TLT", "GLD", "LQD"]},
        "stress":      {"risk_on": ["SPY", "QQQ", "IWM", "HYG"],
                        "defensive": ["BIL", "IEF", "TLT", "LQD", "GLD"]},
        "overheating": {"risk_on": ["GLD", "XLE", "PDBC", "DBA", "TIP"],
                        "defensive": ["BIL", "SHY", "IEF"]},
    }

    for ms in ["expansion", "slowdown", "stress", "overheating"]:
        dev_rows = df_nm[
            (df_nm["label"] == f"neutral_mixed|macro_{ms}|dev") &
            (df_nm["n"] >= 20)
        ].copy()

        if dev_rows.empty:
            buckets[ms] = {
                "data_top": [], "data_bottom": [],
                "intuitive_risk_on": intuitive_buckets[ms]["risk_on"],
                "intuitive_defensive": intuitive_buckets[ms]["defensive"],
                "contradiction": False,
                "n": 0,
            }
            continue

        dev_rows = dev_rows.sort_values("sharpe_4w", ascending=False)
        top_etfs = list(dev_rows.head(5)["etf"])
        bottom_etfs = list(dev_rows.tail(5)["etf"])

        # Check contradiction: do top data-derived ETFs match intuition?
        intu_ro = intuitive_buckets[ms]["risk_on"]
        data_top_is_intu = any(e in intu_ro for e in top_etfs[:3])
        contradiction = not data_top_is_intu

        # ETF stats for reporting
        top_stats = dev_rows.head(5)[["etf", "n", "mean_4w", "sharpe_4w"]].to_dict("records")
        bottom_stats = dev_rows.tail(5)[["etf", "n", "mean_4w", "sharpe_4w"]].to_dict("records")

        print(f"  NM+{ms}: top={top_etfs}, bottom={bottom_etfs}, contradiction={contradiction}")
        if contradiction:
            intu_str = intu_ro[:3]
            print(f"    !! DATA contradicts intuition. Intuitive risk-on: {intu_str}, Data says: {top_etfs[:3]}")

        buckets[ms] = {
            "data_top": top_etfs,
            "data_bottom": bottom_etfs,
            "data_top_stats": top_stats,
            "data_bottom_stats": bottom_stats,
            "intuitive_risk_on": intuitive_buckets[ms]["risk_on"],
            "intuitive_defensive": intuitive_buckets[ms]["defensive"],
            "contradiction": contradiction,
            "n_dev": int(dev_rows["n"].iloc[0]) if len(dev_rows) > 0 else 0,
        }

    return buckets


# ---------------------------------------------------------------------------
# [4] Tilt implementation engine
# ---------------------------------------------------------------------------

def apply_tilt(
    baseline_wts: pd.DataFrame,
    market_state: pd.Series,
    v3: pd.Series,
    credit_ok: pd.Series,
    spy_ok: pd.Series,
    tilt_size: float,
    favored_etfs: dict[str, list[str]],
    variant_family: str,
    tilt_scope: str = "neutral_mixed",
) -> pd.DataFrame:
    """
    Apply a relative ETF tilt to baseline weights in selected weeks.

    Returns tilted weight DataFrame (same shape as baseline_wts).
    Tilt_size: fraction of total portfolio weight to shift (e.g. 0.05 = 5%).
    Favored_etfs: dict macro_state -> list of ETFs to tilt toward.
    """
    tilted = baseline_wts.copy()
    etfs = list(baseline_wts.columns)
    cap = MAX_POSITION_CAP

    for date in baseline_wts.index:
        ms = market_state.get(date, None)
        if ms != tilt_scope:
            continue

        macro = v3.get(date, None)
        if pd.isna(macro) or macro not in favored_etfs:
            continue

        # Variant family gate
        cred = credit_ok.get(date, False)
        spy = spy_ok.get(date, False)

        if variant_family == "A":
            pass  # macro-only, no gate
        elif variant_family == "B":
            if not cred:
                continue  # credit must confirm
        elif variant_family == "C":
            if not spy:
                continue  # SPY trend must confirm
        elif variant_family == "D":
            if not (cred and spy):
                continue  # both must confirm

        favored = [e for e in favored_etfs[macro] if e in etfs]
        if not favored:
            continue

        w = tilted.loc[date].copy()
        total_shift = tilt_size

        # ETFs to draw weight FROM: equal weight from all non-favored, non-BIL ETFs
        # Exclude BIL from being drained to preserve safety floor
        source_pool = [e for e in etfs if e not in favored and e != "BIL" and w[e] > 0]
        if not source_pool:
            source_pool = [e for e in etfs if e not in favored and w[e] > 0]

        total_source = w[source_pool].sum()
        if total_source < total_shift:
            total_shift = total_source * 0.9  # only shift what's available

        # Draw proportionally from source pool
        if total_source > 0:
            for e in source_pool:
                w[e] -= total_shift * (w[e] / total_source)

        # Add to favored ETFs, capped
        per_etf = total_shift / len(favored)
        for e in favored:
            w[e] += per_etf
            if w[e] > cap:
                excess = w[e] - cap
                w[e] = cap
                # Return excess to source pool proportionally
                if source_pool and total_source > 0:
                    for s in source_pool:
                        w[s] += excess * (w[s] / total_source)

        # Enforce long-only and renormalize
        w = w.clip(lower=0)
        total = w.sum()
        if total > 0:
            w = w / total

        tilted.loc[date] = w

    return tilted


def compute_portfolio_returns(
    weights: pd.DataFrame,
    etf_rets: pd.DataFrame,
    prev_weights: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Compute portfolio returns from weights and ETF returns.

    Convention (matches production baseline file):
      gross_return[t] = w[t] @ etf_rets[t+1]
      turnover[t]     = 0.5 * |w[t] - drift(w[t-1], etf_rets[t])|  (rebalance cost at t)
      cost[t]         = turnover[t] * 10bps

    Weights at t are the target weights SET at end of week t, earning returns
    during the following week (t → t+1). Turnover reflects the rebalance from
    last week's drifted position into the new targets.
    """
    dates = weights.index
    # r[t+1] aligned to index t
    etf_rets_next = etf_rets.shift(-1)

    gross_rets = []
    turnovers = []
    costs = []

    w_prev = None

    for i, date in enumerate(dates):
        w = weights.loc[date].fillna(0).values
        # Gross = forward-looking: weights set at t, returns in week t→t+1
        r_next = etf_rets_next.loc[date].reindex(weights.columns).fillna(0).values
        gross = float(np.dot(w, r_next))
        gross_rets.append(gross)

        # Turnover: rebalance at t from drifted w[t-1] to w[t]
        # Drift uses etf_rets[t] = return from t-1 to t
        if w_prev is None:
            to = 0.0
        else:
            r_curr = etf_rets.loc[date].reindex(weights.columns).fillna(0).values
            drift_w = w_prev * (1 + r_curr)
            drift_sum = drift_w.sum()
            if drift_sum > 1e-8:
                drift_w = drift_w / drift_sum
            to = float(np.sum(np.abs(w - drift_w)) / 2)
        turnovers.append(to)
        cost = to * COST_PER_TURNOVER
        costs.append(cost)
        w_prev = w.copy()

    out = pd.DataFrame({
        "gross_return": gross_rets,
        "net_return": [g - c for g, c in zip(gross_rets, costs)],
        "turnover": turnovers,
        "cost": costs,
    }, index=dates)
    out["wealth"] = (1 + out["net_return"]).cumprod()
    out["drawdown"] = out["wealth"] / out["wealth"].cummax() - 1
    return out


# ---------------------------------------------------------------------------
# [5] Build tilt rule definitions
# ---------------------------------------------------------------------------

def build_tilt_rules(buckets: dict) -> list[dict]:
    """Return list of tilt rule dicts: variant_family, macro_state -> favored_etfs, tilt_size."""
    rules = []

    for family in ["A", "B", "C", "D"]:
        for tilt_size in [0.025, 0.05, 0.075, 0.10]:
            name = f"family{family}_tilt{int(tilt_size*100)}pct"

            # For each variant, define favored ETFs per macro state
            # We test both data-derived and intuitive buckets
            for bucket_type in ["data", "intuitive"]:
                favored = {}
                for ms, bk in buckets.items():
                    if bk.get("n_dev", 0) < MIN_OBS_TILT and bucket_type == "data":
                        # Not enough data, skip
                        continue
                    if bucket_type == "data":
                        favored[ms] = bk["data_top"][:3]
                    else:
                        # Intuitive: tilt toward risk-on in expansion/slowdown (if data-derived)
                        # tilt defensive in stress/overheating
                        if ms in ["expansion", "slowdown"]:
                            favored[ms] = bk["intuitive_risk_on"][:3]
                        else:
                            favored[ms] = bk["intuitive_defensive"][:3]

                rules.append({
                    "name": f"{name}_{bucket_type}",
                    "variant_family": family,
                    "tilt_size": tilt_size,
                    "bucket_type": bucket_type,
                    "favored_etfs_by_macro": favored,
                })

    return rules


# ---------------------------------------------------------------------------
# [6] Evaluate all candidates
# ---------------------------------------------------------------------------

def evaluate_candidates(data: dict, rules: list[dict], buckets: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    print(f"\n[5/6] Evaluating {len(rules)} tilt candidates...")

    baseline_rets = data["baseline_rets"]
    baseline_wts = data["baseline_wts"]
    market_state = data["market_state"]
    v3 = data["v3"]
    etf_rets = data["etf_rets"]
    credit_ok = data["credit_trend_improving"]
    spy_ok = data["spy_above_200"]

    v3_macro = v3["macro_state"]

    HOLDOUT_START_TS = HOLDOUT_START
    DEV_END_TS = DEV_END

    metrics_full = []
    metrics_state = []
    metrics_holdout = []
    metrics_turnover = []

    # Baseline metrics
    def get_metrics_row(label, r_series, to_series, period="full"):
        return full_metrics(r_series, to_series, label=label)

    bl_r = baseline_rets["net_return"]
    bl_to = baseline_rets["turnover"]
    bl_base = full_metrics(bl_r, bl_to, label="BASELINE")
    bl_base["variant"] = "baseline"
    bl_base["family"] = "baseline"
    bl_base["tilt_size"] = 0.0
    bl_base["bucket_type"] = "none"
    metrics_full.append(bl_base)

    bl_dev = full_metrics(bl_r[bl_r.index <= DEV_END_TS], bl_to[bl_to.index <= DEV_END_TS], "BASELINE_dev")
    bl_hold = full_metrics(bl_r[bl_r.index >= HOLDOUT_START_TS], bl_to[bl_to.index >= HOLDOUT_START_TS], "BASELINE_holdout")

    # Compute baseline per-state dev metrics
    bl_state_rows = state_metrics(bl_r[bl_r.index <= DEV_END_TS], market_state[market_state.index <= DEV_END_TS], bl_to[bl_to.index <= DEV_END_TS])
    for row in bl_state_rows:
        row["variant"] = "baseline"
        row["period"] = "dev"
        metrics_state.append(row)

    bl_h_state_rows = state_metrics(bl_r[bl_r.index >= HOLDOUT_START_TS], market_state[market_state.index >= HOLDOUT_START_TS], bl_to[bl_to.index >= HOLDOUT_START_TS])
    for row in bl_h_state_rows:
        row["variant"] = "baseline"
        row["period"] = "holdout"
        metrics_state.append(row)

    for rule in rules:
        name = rule["name"]
        family = rule["variant_family"]
        tilt_size = rule["tilt_size"]
        bucket_type = rule["bucket_type"]
        favored = rule["favored_etfs_by_macro"]

        try:
            tilted_wts = apply_tilt(
                baseline_wts=baseline_wts,
                market_state=market_state,
                v3=v3_macro,
                credit_ok=credit_ok,
                spy_ok=spy_ok,
                tilt_size=tilt_size,
                favored_etfs=favored,
                variant_family=family,
            )

            tilted_rets = compute_portfolio_returns(tilted_wts, etf_rets)

            # Full period
            r = tilted_rets["net_return"]
            to = tilted_rets["turnover"]
            m = full_metrics(r, to, label=name)
            m["variant"] = name
            m["family"] = family
            m["tilt_size"] = tilt_size
            m["bucket_type"] = bucket_type
            # Sharpe delta vs baseline
            m["sharpe_delta_vs_baseline"] = round(m["sharpe"] - bl_base["sharpe"], 6)
            m["return_delta_vs_baseline"] = round(m["ann_return"] - bl_base["ann_return"], 6)
            m["dd_delta_vs_baseline"] = round(m["max_drawdown"] - bl_base["max_drawdown"], 6)
            metrics_full.append(m)

            # Turnover
            to_row = {
                "variant": name,
                "family": family,
                "tilt_size": tilt_size,
                "bucket_type": bucket_type,
                "avg_weekly_turnover": round(float(to.mean()), 6),
                "ann_turnover": round(float(to.mean() * 52), 6),
                "avg_weekly_cost": round(float((to * COST_PER_TURNOVER).mean()), 6),
                "ann_cost_drag": round(float(to.mean() * COST_PER_TURNOVER * 52), 6),
                "baseline_ann_turnover": round(float(bl_to.mean() * 52), 6),
                "turnover_increase_ann": round(float((to.mean() - bl_to.mean()) * 52), 6),
            }
            metrics_turnover.append(to_row)

            # Holdout
            r_hold = r[r.index >= HOLDOUT_START_TS]
            to_hold = to[to.index >= HOLDOUT_START_TS]
            mh = full_metrics(r_hold, to_hold, label=f"{name}_holdout")
            mh["variant"] = name
            mh["family"] = family
            mh["tilt_size"] = tilt_size
            mh["bucket_type"] = bucket_type
            mh["holdout_sharpe_delta_vs_baseline"] = round(mh["sharpe"] - bl_hold["sharpe"], 6)
            metrics_holdout.append(mh)

            # State breakdown (dev)
            r_dev = r[r.index <= DEV_END_TS]
            to_dev = to[to.index <= DEV_END_TS]
            ms_dev = market_state[market_state.index <= DEV_END_TS]
            state_rows = state_metrics(r_dev, ms_dev, to_dev)
            for row in state_rows:
                row["variant"] = name
                row["family"] = family
                row["tilt_size"] = tilt_size
                row["bucket_type"] = bucket_type
                row["period"] = "dev"
                metrics_state.append(row)

            # State breakdown (holdout)
            r_hold2 = r[r.index >= HOLDOUT_START_TS]
            to_hold2 = to[to.index >= HOLDOUT_START_TS]
            ms_hold = market_state[market_state.index >= HOLDOUT_START_TS]
            h_state_rows = state_metrics(r_hold2, ms_hold, to_hold2)
            for row in h_state_rows:
                row["variant"] = name
                row["family"] = family
                row["tilt_size"] = tilt_size
                row["bucket_type"] = bucket_type
                row["period"] = "holdout"
                metrics_state.append(row)

        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            continue

        status = "✓" if m["sharpe_delta_vs_baseline"] > 0 else "✗"
        print(f"  {status} {name}: Sharpe={m['sharpe']:.4f} (Δ={m['sharpe_delta_vs_baseline']:+.4f}), "
              f"AnnRet={m['ann_return']:.4%}, MaxDD={m['max_drawdown']:.4%}")

    return metrics_full, metrics_state, metrics_holdout, metrics_turnover


# ---------------------------------------------------------------------------
# [7] Pass/fail gates
# ---------------------------------------------------------------------------

def apply_gates(metrics_full: list[dict], metrics_holdout: list[dict], metrics_state: list[dict],
                metrics_turnover: list[dict]) -> pd.DataFrame:
    print("\n[7] Applying pass/fail gates...")

    df_full = pd.DataFrame(metrics_full)
    df_hold = pd.DataFrame(metrics_holdout)
    df_state = pd.DataFrame(metrics_state)
    df_turn = pd.DataFrame(metrics_turnover)

    baseline_full = df_full[df_full["variant"] == "baseline"].iloc[0]
    baseline_hold = df_hold[df_hold["variant"] == "baseline"].iloc[0] if "baseline" in df_hold["variant"].values else None

    results = []
    candidates = df_full[df_full["variant"] != "baseline"]

    for _, row in candidates.iterrows():
        variant = row["variant"]

        # Get holdout metrics
        hold_row = df_hold[df_hold["variant"] == variant]
        h_sharpe = hold_row["sharpe"].iloc[0] if not hold_row.empty else np.nan

        # Get NM dev state metrics
        nm_dev = df_state[(df_state["variant"] == variant) & (df_state["period"] == "dev") & (df_state["state"] == "neutral_mixed")]
        nm_sharpe = nm_dev["sharpe"].iloc[0] if not nm_dev.empty else np.nan
        bl_nm_dev = df_state[(df_state["variant"] == "baseline") & (df_state["period"] == "dev") & (df_state["state"] == "neutral_mixed")]
        bl_nm_sharpe = bl_nm_dev["sharpe"].iloc[0] if not bl_nm_dev.empty else np.nan

        # Stressed_panic dev metrics
        sp_dev = df_state[(df_state["variant"] == variant) & (df_state["period"] == "dev") & (df_state["state"] == "stressed_panic")]
        sp_sharpe = sp_dev["sharpe"].iloc[0] if not sp_dev.empty else np.nan
        bl_sp = df_state[(df_state["variant"] == "baseline") & (df_state["period"] == "dev") & (df_state["state"] == "stressed_panic")]
        bl_sp_sharpe = bl_sp["sharpe"].iloc[0] if not bl_sp.empty else np.nan

        # Turnover
        turn_row = df_turn[df_turn["variant"] == variant]
        to_increase = turn_row["turnover_increase_ann"].iloc[0] if not turn_row.empty else np.nan

        # Gate evaluation
        g1 = (row["sharpe"] - baseline_full["sharpe"]) >= 0.01
        g2 = h_sharpe >= baseline_full["sharpe"] - 0.01 if not np.isnan(h_sharpe) else False
        g3 = row["ann_return"] >= baseline_full["ann_return"] - 0.002
        g4 = (row["max_drawdown"] - baseline_full["max_drawdown"]) <= 0.01
        g5 = (row["cvar_5pct"] - baseline_full["cvar_5pct"]) >= -0.005
        g6 = to_increase <= 0.03 if not np.isnan(to_increase) else False
        g7 = nm_sharpe > bl_nm_sharpe if not np.isnan(nm_sharpe) and not np.isnan(bl_nm_sharpe) else False
        g8 = (sp_sharpe - bl_sp_sharpe) >= -0.02 if not np.isnan(sp_sharpe) else False
        g9 = not (row.get("max_drawdown", 0) < baseline_full["max_drawdown"] - 0.015)  # no hidden leverage

        gates_passed = sum([g1, g2, g3, g4, g5, g6, g7, g8, g9])
        all_gates = all([g1, g2, g3, g4, g5, g6, g7, g8, g9])

        if all_gates:
            verdict = "PROMOTE_TO_PHASE_D_TEST"
        elif g7 and (gates_passed >= 6):
            verdict = "RESEARCH-ONLY"
        elif g7 and (gates_passed >= 4):
            verdict = "RESEARCH-ONLY"
        else:
            verdict = "DROP"

        results.append({
            "variant": variant,
            "family": row["family"],
            "tilt_size": row["tilt_size"],
            "bucket_type": row["bucket_type"],
            "full_sharpe": round(row["sharpe"], 4),
            "sharpe_delta": round(row["sharpe"] - baseline_full["sharpe"], 4),
            "ann_return": round(row["ann_return"], 4),
            "max_drawdown": round(row["max_drawdown"], 4),
            "holdout_sharpe": round(h_sharpe, 4) if not np.isnan(h_sharpe) else None,
            "nm_dev_sharpe": round(nm_sharpe, 4) if not np.isnan(nm_sharpe) else None,
            "nm_improved": g7,
            "turnover_increase_ann": round(to_increase, 4) if not np.isnan(to_increase) else None,
            "g1_sharpe_+001": g1,
            "g2_holdout_ok": g2,
            "g3_return_ok": g3,
            "g4_dd_ok": g4,
            "g5_cvar_ok": g5,
            "g6_turnover_ok": g6,
            "g7_nm_improved": g7,
            "g8_sp_ok": g8,
            "g9_no_leverage": g9,
            "gates_passed": gates_passed,
            "verdict": verdict,
        })

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values("sharpe_delta", ascending=False)
    return df_results


# ---------------------------------------------------------------------------
# [8] Robustness checks for top candidates
# ---------------------------------------------------------------------------

def robustness_checks(data: dict, top_candidates: list[str], rules: list[dict],
                      gates_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    print(f"\n[8] Robustness checks for top {len(top_candidates)} candidates...")

    baseline_rets = data["baseline_rets"]
    baseline_wts = data["baseline_wts"]
    market_state = data["market_state"]
    v3 = data["v3"]
    etf_rets = data["etf_rets"]
    credit_ok = data["credit_trend_improving"]
    spy_ok = data["spy_above_200"]
    v3_macro = v3["macro_state"]

    bl_r = baseline_rets["net_return"]
    bl_to = baseline_rets["turnover"]

    rows = []

    for cand_name in top_candidates:
        rule = next((r for r in rules if r["name"] == cand_name), None)
        if rule is None:
            continue

        tilted_wts = apply_tilt(
            baseline_wts, market_state, v3_macro, credit_ok, spy_ok,
            rule["tilt_size"], rule["favored_etfs_by_macro"], rule["variant_family"]
        )
        tilted_rets = compute_portfolio_returns(tilted_wts, etf_rets)
        r = tilted_rets["net_return"]
        to = tilted_rets["turnover"]

        def add_row(label, mask):
            sub_r = r[mask].dropna()
            sub_to = to[mask]
            bl_sub = bl_r[mask].dropna()
            m = full_metrics(sub_r, sub_to, label)
            m["candidate"] = cand_name
            m["window"] = label
            m["bl_sharpe"] = round(sharpe(bl_sub), 4)
            m["sharpe_delta"] = round(m["sharpe"] - m["bl_sharpe"], 4) if not np.isnan(m["sharpe"]) else None
            rows.append(m)

        # Holdout
        add_row("holdout_2024_onwards", r.index >= HOLDOUT_START)
        # Dev
        add_row("dev_thru_2024", r.index <= DEV_END)
        # Excluding 2020
        mask_ex2020 = ~((r.index >= "2020-02-01") & (r.index <= "2020-06-30"))
        add_row("dev_ex_2020", (r.index <= DEV_END) & mask_ex2020)
        # Excluding 2022
        mask_ex2022 = ~((r.index >= "2022-01-01") & (r.index <= "2022-12-31"))
        add_row("dev_ex_2022", (r.index <= DEV_END) & mask_ex2022)
        # Pre-2010
        add_row("pre_2010", r.index < "2010-01-01")
        # 2010-2019
        add_row("decade_2010s", (r.index >= "2010-01-01") & (r.index < "2020-01-01"))
        # Post-2020
        add_row("post_2020_dev", (r.index >= "2020-01-01") & (r.index <= DEV_END))

        # Sensitivity to tilt size
        for alt_size in [rule["tilt_size"] * 0.5, rule["tilt_size"] * 1.5]:
            alt_wts = apply_tilt(
                baseline_wts, market_state, v3_macro, credit_ok, spy_ok,
                alt_size, rule["favored_etfs_by_macro"], rule["variant_family"]
            )
            alt_rets = compute_portfolio_returns(alt_wts, etf_rets)
            alt_r = alt_rets["net_return"]
            alt_to = alt_rets["turnover"]
            m = full_metrics(alt_r, alt_to, f"alt_tilt_{alt_size:.3f}")
            m["candidate"] = cand_name
            m["window"] = f"sensitivity_tilt_{alt_size:.3f}"
            m["bl_sharpe"] = round(sharpe(bl_r), 4)
            m["sharpe_delta"] = round(m["sharpe"] - m["bl_sharpe"], 4)
            rows.append(m)

        # Sensitivity to 2x transaction costs
        class HighCostPortfolio:
            pass

        high_cost_rets = tilted_rets.copy()
        high_cost_rets["net_return"] = high_cost_rets["gross_return"] - high_cost_rets["turnover"] * COST_PER_TURNOVER * 2
        m2 = full_metrics(high_cost_rets["net_return"], high_cost_rets["turnover"], "2x_cost")
        m2["candidate"] = cand_name
        m2["window"] = "sensitivity_2x_cost"
        m2["bl_sharpe"] = round(sharpe(bl_r), 4)
        m2["sharpe_delta"] = round(m2["sharpe"] - m2["bl_sharpe"], 4)
        rows.append(m2)

        gate_row = gates_df[gates_df["variant"] == cand_name]
        verdict = gate_row["verdict"].iloc[0] if not gate_row.empty else "UNKNOWN"
        hold_sh = rows[-8].get("sharpe", float("nan")) if len(rows) >= 8 else float("nan")
        hold_sh_str = f"{hold_sh:.3f}" if not (hold_sh != hold_sh) else "N/A"
        print(f"  {cand_name}: verdict={verdict}, holdout_sharpe={hold_sh_str}")

    df_rob = pd.DataFrame(rows)
    return df_rob, _build_robustness_md(df_rob, top_candidates, gates_df)


def _build_robustness_md(df: pd.DataFrame, top_candidates: list[str], gates_df: pd.DataFrame) -> str:
    lines = ["# Top Candidate Robustness Checks\n"]
    lines.append(f"**Sprint date:** 2026-06-06\n")
    lines.append(f"**Top candidates reviewed:** {len(top_candidates)}\n\n")

    for cand in top_candidates:
        gate_row = gates_df[gates_df["variant"] == cand]
        verdict = gate_row["verdict"].iloc[0] if not gate_row.empty else "UNKNOWN"
        lines.append(f"## {cand}\n")
        lines.append(f"**Gate verdict:** `{verdict}`\n\n")

        sub = df[df["candidate"] == cand][["window", "sharpe", "bl_sharpe", "sharpe_delta", "max_drawdown", "ann_return", "n_weeks"]]
        lines.append(sub.to_string(index=False))
        lines.append("\n\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# [9] Summary JSON and notes
# ---------------------------------------------------------------------------

def build_summary_json(gates_df: pd.DataFrame, bl_full: dict, top3: list[str]) -> dict:
    best = gates_df.iloc[0] if not gates_df.empty else {}
    promote_count = int((gates_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    ro_count = int((gates_df["verdict"] == "RESEARCH-ONLY").sum())
    drop_count = int((gates_df["verdict"] == "DROP").sum())
    nm_improved_count = int(gates_df["nm_improved"].sum())

    if promote_count > 0:
        overall_verdict = "PROMOTE_TO_PHASE_D_TEST"
    elif ro_count > 0:
        overall_verdict = "RESEARCH-ONLY"
    else:
        overall_verdict = "DROP"

    return {
        "sprint": "macro_conditioned_etf_tilt_sandbox",
        "date": "2026-06-06",
        "production_pin": PIN,
        "overall_verdict": overall_verdict,
        "baseline_sharpe": round(bl_full["sharpe"], 4),
        "baseline_ann_return": round(bl_full["ann_return"], 4),
        "baseline_max_dd": round(bl_full["max_drawdown"], 4),
        "n_candidates": len(gates_df),
        "promote_count": promote_count,
        "research_only_count": ro_count,
        "drop_count": drop_count,
        "nm_improved_count": nm_improved_count,
        "best_variant": best.get("variant", "none"),
        "best_sharpe_delta": round(float(best.get("sharpe_delta", 0)), 4),
        "best_nm_sharpe": round(float(best.get("nm_dev_sharpe", 0)), 4) if best.get("nm_dev_sharpe") else None,
        "top3_candidates": top3,
    }


def write_notes(summary: dict, gates_df: pd.DataFrame, buckets: dict, bl_full: dict,
                df_full: pd.DataFrame, df_hold: pd.DataFrame, df_state: pd.DataFrame) -> str:
    verdict = summary["overall_verdict"]
    best = gates_df.iloc[0] if not gates_df.empty else {}

    # Baseline NM stats
    bl_nm = df_state[(df_state["variant"] == "baseline") & (df_state["period"] == "dev") & (df_state["state"] == "neutral_mixed")]
    bl_nm_sharpe = bl_nm["sharpe"].iloc[0] if not bl_nm.empty else np.nan

    lines = [
        "# Macro-Conditioned ETF Tilt Sandbox — Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-06",
        f"**Verdict:** `{verdict}`",
        "",
        "---",
        "",
        "## 1. Which ETFs performed best inside neutral_mixed + each V3 macro state?",
        "",
        "Derived from dev period only (not holdout). Top 3 by annualized Sharpe:",
        "",
    ]

    for ms in ["expansion", "slowdown", "stress", "overheating"]:
        bk = buckets.get(ms, {})
        top = bk.get("data_top", [])[:3]
        stats = bk.get("data_top_stats", [])[:3]
        stat_str = ", ".join([f"{s['etf']}({s['sharpe_4w']:.2f})" for s in stats[:3]]) if stats else "N/A"
        lines.append(f"- **NM + {ms}**: {stat_str}")
        if bk.get("contradiction"):
            intu = bk.get("intuitive_risk_on", [])[:3]
            lines.append(f"  - !! Data contradicts intuition: intuitive risk-on = {intu}, data says = {top}")

    lines += [
        "",
        "## 2. Did the data confirm or contradict intuitive macro ETF buckets?",
        "",
    ]
    for ms, bk in buckets.items():
        contr = bk.get("contradiction", False)
        lines.append(f"- **{ms}**: {'CONTRADICTION' if contr else 'Broadly consistent'}")

    lines += [
        "",
        "## 3. Which tilt variant performed best?",
        "",
    ]
    if not gates_df.empty:
        top5 = gates_df.head(5)[["variant", "full_sharpe", "sharpe_delta", "ann_return", "nm_dev_sharpe", "verdict"]]
        lines.append("| Variant | Sharpe | ΔSharpe | Ann Return | NM Sharpe | Verdict |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for _, r in top5.iterrows():
            lines.append(f"| {r['variant']} | {r['full_sharpe']:.4f} | {r['sharpe_delta']:+.4f} | "
                         f"{r['ann_return']:.4%} | {r.get('nm_dev_sharpe','N/A')} | {r['verdict']} |")

    lines += [
        "",
        "## 4. Which diagnostic family worked best?",
        "",
    ]
    for fam in ["A", "B", "C", "D"]:
        sub = gates_df[gates_df["family"] == fam]
        if sub.empty:
            continue
        best_row = sub.iloc[0]
        lines.append(f"- **Family {fam}**: best Sharpe delta = {best_row['sharpe_delta']:+.4f} ({best_row['variant']})")

    lines += [
        "",
        "## 5. Did any candidate improve neutral_mixed without hurting full portfolio?",
        "",
        f"Baseline NM dev Sharpe: {bl_nm_sharpe:.3f}" if not np.isnan(bl_nm_sharpe) else "Baseline NM dev Sharpe: N/A",
        f"Candidates with NM improvement: {summary['nm_improved_count']} of {summary['n_candidates']}",
        "",
    ]

    lines += [
        "",
        "## 6. Did any candidate clear the promotion gates?",
        "",
        f"PROMOTE_TO_PHASE_D_TEST: {summary['promote_count']}",
        f"RESEARCH-ONLY: {summary['research_only_count']}",
        f"DROP: {summary['drop_count']}",
        "",
    ]

    if summary["promote_count"] > 0:
        promoted = gates_df[gates_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST"]
        for _, pr in promoted.iterrows():
            lines.append(f"- PROMOTED: `{pr['variant']}` — Sharpe Δ={pr['sharpe_delta']:+.4f}, NM Sharpe={pr.get('nm_dev_sharpe','N/A')}")

    lines += [
        "",
        "## 7. Best tilt size?",
        "",
    ]
    for sz in [0.025, 0.05, 0.075, 0.10]:
        sub = gates_df[gates_df["tilt_size"] == sz]
        if sub.empty:
            continue
        best_in_sz = sub.iloc[0]
        lines.append(f"- **{int(sz*100)}%**: best Sharpe delta = {best_in_sz['sharpe_delta']:+.4f} ({best_in_sz['verdict']})")

    lines += [
        "",
        "## 8. Did turnover or transaction costs erase the benefit?",
        "",
    ]
    if not gates_df.empty:
        top_row = gates_df.iloc[0]
        to_inc = top_row.get("turnover_increase_ann", np.nan)
        if not np.isnan(float(to_inc)) if to_inc is not None else False:
            lines.append(f"Best candidate turnover increase (ann): {float(to_inc):.4f}")
            lines.append(f"Gate 6 (≤3pp increase): {'PASS' if top_row.get('g6_turnover_ok') else 'FAIL'}")

    lines += [
        "",
        "## 9. Holdout and robustness",
        "",
        f"Holdout available: 104 weeks (2024-04-19 to 2026-04-10)",
        f"Baseline holdout Sharpe: {bl_full.get('holdout_sharpe', 'N/A')}",
        "",
        "All holdout classification was slowdown (97 weeks) — V3 saw no expansion/stress/overheating in holdout.",
        "This severely limits holdout discrimination for macro-state tilts.",
        "",
    ]

    lines += [
        "",
        "## 10. Final Verdict",
        "",
        f"**`{verdict}`**",
        "",
        "| Gate | Criterion | Best Candidate |",
        "| --- | --- | --- |",
        f"| G1: Sharpe +0.01 | {gates_df.iloc[0]['g1_sharpe_+001'] if not gates_df.empty else 'N/A'} | {best.get('variant','N/A')} |" if not gates_df.empty else "| G1 | N/A | N/A |",
        f"| G2: Holdout Sharpe OK | {gates_df.iloc[0]['g2_holdout_ok'] if not gates_df.empty else 'N/A'} | |",
        f"| G7: NM Improved | {gates_df.iloc[0]['g7_nm_improved'] if not gates_df.empty else 'N/A'} | |",
        "",
        "---",
        "*Research artifact sprint — no production artifacts modified.*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("MACRO-CONDITIONED ETF TILT SANDBOX — STEP 2")
    print("=" * 70)

    # Load
    data = load_data()

    # Asset diagnostics
    df_all, df_nm = build_asset_diagnostics(data)

    # Tilt buckets from dev data
    buckets = derive_tilt_buckets(df_nm)

    # Write tilt rule definitions markdown
    rule_md_lines = ["# Tilt Rule Definitions\n",
                     "**Sprint:** macro_conditioned_etf_tilt_sandbox (Step 2)\n",
                     "**Date:** 2026-06-06\n",
                     "",
                     "## Variant Families",
                     "- **A**: Macro state only (no confirmation gate)",
                     "- **B**: Macro state + credit trend improving (HYG/LQD 4w momentum)",
                     "- **C**: Macro state + SPY above 40-week MA",
                     "- **D**: Macro state + credit AND SPY trend (most conservative)",
                     "",
                     "## Tilt Sizes Tested",
                     "2.5%, 5.0%, 7.5%, 10.0%",
                     "",
                     "## Bucket Types",
                     "- **data**: top ETFs from dev-period neutral_mixed asset diagnostics",
                     "- **intuitive**: risk-on/defensive buckets from macro intuition",
                     "",
                     "## Data-Derived Buckets (neutral_mixed, dev only)\n",
                     ]
    for ms, bk in buckets.items():
        rule_md_lines.append(f"### NM + {ms}")
        rule_md_lines.append(f"- Data top ETFs: {bk.get('data_top', [])[:3]}")
        rule_md_lines.append(f"- Intuitive risk-on: {bk.get('intuitive_risk_on', [])[:3]}")
        rule_md_lines.append(f"- Contradiction: {bk.get('contradiction', False)}")
        rule_md_lines.append("")

    (OUT_DIR / "tilt_rule_definitions.md").write_text("\n".join(rule_md_lines))
    print("\n  Saved: tilt_rule_definitions.md")

    # Build rules
    rules = build_tilt_rules(buckets)
    print(f"\n[4] Total tilt rules to test: {len(rules)}")

    # Evaluate
    metrics_full, metrics_state, metrics_holdout, metrics_turnover = evaluate_candidates(data, rules, buckets)

    # Save raw CSVs
    df_full = pd.DataFrame(metrics_full)
    df_state_df = pd.DataFrame(metrics_state)
    df_hold = pd.DataFrame(metrics_holdout)
    df_turn = pd.DataFrame(metrics_turnover)

    df_full.to_csv(OUT_DIR / "candidate_metrics.csv", index=False)
    df_state_df.to_csv(OUT_DIR / "candidate_state_metrics.csv", index=False)
    df_hold.to_csv(OUT_DIR / "candidate_holdout_metrics.csv", index=False)
    df_turn.to_csv(OUT_DIR / "candidate_turnover_costs.csv", index=False)
    print("\n  Saved: candidate_metrics.csv, candidate_state_metrics.csv, "
          "candidate_holdout_metrics.csv, candidate_turnover_costs.csv")

    # Gates
    gates_df = apply_gates(metrics_full, metrics_holdout, df_state_df, df_turn)
    gates_df.to_csv(OUT_DIR / "candidate_gate_results.csv", index=False)
    print(f"\n  Saved: candidate_gate_results.csv")

    # Top 3 candidates by Sharpe delta
    top3_names = list(gates_df["variant"].head(3))
    print(f"\n  Top 3 candidates: {top3_names}")

    # Robustness
    rob_df, rob_md = robustness_checks(data, top3_names, rules, gates_df)
    rob_df.to_csv(OUT_DIR / "top_candidate_robustness.csv", index=False)
    (OUT_DIR / "top_candidate_robustness.md").write_text(rob_md)
    print("  Saved: top_candidate_robustness.csv, top_candidate_robustness.md")

    # Baseline full metrics for summary
    bl_row = df_full[df_full["variant"] == "baseline"].iloc[0].to_dict()
    bl_hold = df_hold[df_hold["variant"] == "baseline"].iloc[0].to_dict() if "baseline" in df_hold["variant"].values else {}
    bl_row["holdout_sharpe"] = bl_hold.get("sharpe", np.nan)

    # Summary JSON
    summary = build_summary_json(gates_df, bl_row, top3_names)
    with open(OUT_DIR / "macro_conditioned_etf_tilt_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("  Saved: macro_conditioned_etf_tilt_summary.json")

    # Notes
    notes_md = write_notes(summary, gates_df, buckets, bl_row, df_full, df_hold, df_state_df)
    (OUT_DIR / "macro_conditioned_etf_tilt_notes.md").write_text(notes_md)
    print("  Saved: macro_conditioned_etf_tilt_notes.md")

    # Print final verdict
    print("\n" + "=" * 70)
    print(f"STEP 2 COMPLETE — OVERALL VERDICT: {summary['overall_verdict']}")
    print("=" * 70)
    print(f"  Baseline: Sharpe={bl_row['sharpe']:.4f}, AnnRet={bl_row['ann_return']:.4%}, MaxDD={bl_row['max_drawdown']:.4%}")
    print(f"  Candidates evaluated: {summary['n_candidates']}")
    print(f"  PROMOTE_TO_PHASE_D_TEST: {summary['promote_count']}")
    print(f"  RESEARCH-ONLY: {summary['research_only_count']}")
    print(f"  DROP: {summary['drop_count']}")
    if not gates_df.empty:
        best = gates_df.iloc[0]
        print(f"  Best candidate: {best['variant']} — Sharpe Δ={best['sharpe_delta']:+.4f}, verdict={best['verdict']}")


if __name__ == "__main__":
    main()
