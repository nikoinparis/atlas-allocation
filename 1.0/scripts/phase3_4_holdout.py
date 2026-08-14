"""Phase 3.4 — holdout discipline + tail-focused candidate validation.

Pre-declared holdout window: HOLDOUT_START onward (last 2 years).
Development window (pre-holdout): everything from `active_start` up to but not
including HOLDOUT_START.

For A, F, Combo1 (current conditional), and the three Phase 3.4 candidates
(T1, T2, T3), we compute:

  * Full-history metrics (Sharpe, ann return, ann vol, max DD, Calmar, CVaR 5%)
  * Pre-holdout metrics (development window)
  * Holdout metrics
  * Deltas Combo1-vs-A, T*-vs-Combo1, T*-vs-A, T*-vs-F  in each window

Also runs a 13-week block bootstrap on the Sharpe and max-DD differences
between each candidate and A, on the holdout window only, so we can ask
whether a candidate's apparent holdout edge is statistically credible.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
OUT_DIR = ROOT / "docs" / "research" / "phase3_4_artifacts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Pre-declared holdout: last ~2 years of available weekly data.
HOLDOUT_START = pd.Timestamp("2024-04-19")

A_NAME = "improved_phase2b_regime_confidence_boost"
F_NAME = "improved_phase2b_combo_abc"
C_NAME = "improved_phase3_1_combo_c1a_a1g"
T1_NAME = "improved_phase3_4_combo_fragile_guard"
T2_NAME = "improved_phase3_4_combo_tilt_dampened"
T3_NAME = "improved_phase3_4_combo_fragile_guard_tilt_dampened"

VERSIONS = [A_NAME, F_NAME, C_NAME, T1_NAME, T2_NAME, T3_NAME]


def read_net_returns(version_name: str) -> pd.Series:
    fp = L3_DIR / f"portfolio_version_returns_{version_name}.csv"
    df = pd.read_csv(fp, index_col=0, parse_dates=True)
    s = df["net_return"].astype(float)
    s.name = version_name
    return s


def sharpe_annualized(r: pd.Series) -> float:
    r = r.dropna()
    if r.std(ddof=0) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=0) * math.sqrt(52))


def annret(r: pd.Series) -> float:
    r = r.dropna()
    w = (1.0 + r).prod()
    n = len(r)
    if n <= 0:
        return 0.0
    return float(w ** (52.0 / n) - 1.0)


def annvol(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.std(ddof=0) * math.sqrt(52)) if len(r) > 1 else 0.0


def maxdd_from(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) == 0:
        return 0.0
    wealth = (1.0 + r).cumprod()
    roll_max = wealth.cummax()
    dd = wealth / roll_max - 1.0
    return float(dd.min())


def cvar5(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) == 0:
        return 0.0
    q = r.quantile(0.05)
    tail = r[r <= q]
    if len(tail) == 0:
        return 0.0
    return float(tail.mean())


def calmar(r: pd.Series) -> float:
    ar = annret(r)
    mdd = maxdd_from(r)
    return float(ar / abs(mdd)) if mdd < 0 else float("nan")


def metrics_block(r: pd.Series) -> dict:
    return {
        "n_weeks": int(r.dropna().shape[0]),
        "ann_return": annret(r),
        "ann_vol": annvol(r),
        "sharpe": sharpe_annualized(r),
        "max_drawdown": maxdd_from(r),
        "calmar": calmar(r),
        "cvar_5": cvar5(r),
    }


# ---- load all six series, align ----
series = {v: read_net_returns(v) for v in VERSIONS}
rets = pd.concat(series.values(), axis=1).dropna()
# Drop pure-zero warmup rows
active_start = rets[(rets != 0).any(axis=1)].index.min()
rets = rets.loc[active_start:]

full_index = rets.index
dev = rets.loc[:HOLDOUT_START - pd.Timedelta(days=1)]
hold = rets.loc[HOLDOUT_START:]


window_blocks = {}
for window_name, window_df in [("full_history", rets), ("pre_holdout", dev), ("holdout", hold)]:
    block = {
        "date_min": str(window_df.index.min().date()) if len(window_df) else None,
        "date_max": str(window_df.index.max().date()) if len(window_df) else None,
        "n_weeks": int(len(window_df)),
        "versions": {},
    }
    for v in VERSIONS:
        block["versions"][v] = metrics_block(window_df[v])
    window_blocks[window_name] = block


# ---- pairwise deltas vs A, F, Combo1 within each window ----
delta_tables = {}
for window_name, block in window_blocks.items():
    deltas = {}
    a = block["versions"][A_NAME]
    f = block["versions"][F_NAME]
    c = block["versions"][C_NAME]
    for v in VERSIONS:
        m = block["versions"][v]
        deltas[v] = {
            "vs_A": {
                "sharpe":       m["sharpe"]       - a["sharpe"],
                "ann_return":   m["ann_return"]   - a["ann_return"],
                "max_drawdown": m["max_drawdown"] - a["max_drawdown"],
                "cvar_5":       m["cvar_5"]       - a["cvar_5"],
                "calmar":       m["calmar"]       - a["calmar"],
            },
            "vs_F": {
                "sharpe":       m["sharpe"]       - f["sharpe"],
                "ann_return":   m["ann_return"]   - f["ann_return"],
                "max_drawdown": m["max_drawdown"] - f["max_drawdown"],
                "cvar_5":       m["cvar_5"]       - f["cvar_5"],
                "calmar":       m["calmar"]       - f["calmar"],
            },
            "vs_Combo1": {
                "sharpe":       m["sharpe"]       - c["sharpe"],
                "ann_return":   m["ann_return"]   - c["ann_return"],
                "max_drawdown": m["max_drawdown"] - c["max_drawdown"],
                "cvar_5":       m["cvar_5"]       - c["cvar_5"],
                "calmar":       m["calmar"]       - c["calmar"],
            },
        }
    delta_tables[window_name] = deltas


# ---- holdout bootstrap: candidate vs A on Sharpe & DD ----
def block_bootstrap_indices(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(math.ceil(n / block_len))
    starts = rng.integers(low=0, high=max(1, n - block_len + 1), size=n_blocks)
    idx = np.concatenate([np.arange(s, s + block_len) for s in starts])[:n]
    return idx


def bootstrap_diff(r_t: pd.Series, r_b: pd.Series, stat_fn, n_iter=2000, block_len=13, seed=20260419):
    rng = np.random.default_rng(seed)
    n = len(r_t)
    if n == 0:
        return {"n": 0}
    diffs = np.empty(n_iter)
    t_vals = r_t.values
    b_vals = r_b.values
    for i in range(n_iter):
        idx = block_bootstrap_indices(n, block_len, rng)
        diffs[i] = stat_fn(pd.Series(t_vals[idx])) - stat_fn(pd.Series(b_vals[idx]))
    return {
        "n": int(n),
        "mean_diff": float(np.mean(diffs)),
        "ci_2_5": float(np.quantile(diffs, 0.025)),
        "ci_97_5": float(np.quantile(diffs, 0.975)),
        "p_target_beats_base": float(np.mean(diffs > 0)),
    }


bootstrap_out = {}
for window_name, window_df in [("holdout", hold), ("pre_holdout", dev), ("full_history", rets)]:
    block = {}
    for v in VERSIONS:
        if v in (A_NAME, F_NAME):
            continue
        block[f"{v}_sharpe_vs_A"] = bootstrap_diff(
            window_df[v], window_df[A_NAME], sharpe_annualized,
        )
        block[f"{v}_ann_return_vs_A"] = bootstrap_diff(
            window_df[v], window_df[A_NAME], annret,
        )
        block[f"{v}_max_dd_vs_A"] = bootstrap_diff(
            window_df[v], window_df[A_NAME], maxdd_from,
        )
    bootstrap_out[window_name] = block

payload = {
    "holdout_start": str(HOLDOUT_START.date()),
    "windows": window_blocks,
    "deltas": delta_tables,
    "bootstrap": bootstrap_out,
}

with (OUT_DIR / "phase3_4_holdout.json").open("w") as f:
    json.dump(payload, f, indent=2, default=str)

# ---- summary printout ----
def fmt(x, w=10, prec=4):
    try:
        return f"{x: .{prec}f}".rjust(w)
    except Exception:
        return str(x).rjust(w)


lines = [f"Phase 3.4 holdout = {HOLDOUT_START.date()} onward"]
for window_name, block in window_blocks.items():
    lines.append(f"\n=== {window_name}  [{block['date_min']} .. {block['date_max']}]  n={block['n_weeks']} ===")
    lines.append(f"{'version':60s}  {'ann_ret':>9s}  {'ann_vol':>9s}  {'sharpe':>9s}  "
                 f"{'max_dd':>9s}  {'calmar':>9s}  {'cvar5':>9s}")
    for v in VERSIONS:
        m = block["versions"][v]
        lines.append(
            f"{v:60s}  {m['ann_return']:9.4f}  {m['ann_vol']:9.4f}  {m['sharpe']:9.3f}  "
            f"{m['max_drawdown']:9.4f}  {m['calmar']:9.3f}  {m['cvar_5']:9.4f}"
        )

lines.append("\n=== Deltas vs A (sharpe / ann_ret / max_dd) ===")
for window_name in ("full_history", "pre_holdout", "holdout"):
    lines.append(f"  window = {window_name}")
    dtbl = delta_tables[window_name]
    for v in VERSIONS:
        if v == A_NAME:
            continue
        d = dtbl[v]["vs_A"]
        lines.append(f"    {v:60s}  dSharpe={d['sharpe']:+.4f}  "
                     f"dRet={d['ann_return']:+.4f}  dDD={d['max_drawdown']:+.4f}  "
                     f"dCvar={d['cvar_5']:+.4f}  dCalmar={d['calmar']:+.4f}")

lines.append("\n=== Deltas vs Combo1 (T* only) ===")
for window_name in ("full_history", "pre_holdout", "holdout"):
    lines.append(f"  window = {window_name}")
    dtbl = delta_tables[window_name]
    for v in (T1_NAME, T2_NAME, T3_NAME):
        d = dtbl[v]["vs_Combo1"]
        lines.append(f"    {v:60s}  dSharpe={d['sharpe']:+.4f}  "
                     f"dRet={d['ann_return']:+.4f}  dDD={d['max_drawdown']:+.4f}  "
                     f"dCvar={d['cvar_5']:+.4f}  dCalmar={d['calmar']:+.4f}")

lines.append("\n=== Holdout block bootstrap vs A (13w blocks, 2000 iter) ===")
holdout_bs = bootstrap_out["holdout"]
for key, res in holdout_bs.items():
    if "n" not in res:
        continue
    lines.append(
        f"  {key:55s}  n={res['n']:3d}  mean_d={res['mean_diff']:+.4f}  "
        f"CI95=[{res['ci_2_5']:+.4f},{res['ci_97_5']:+.4f}]  P(t>b)={res['p_target_beats_base']:.3f}"
    )

text = "\n".join(lines)
print(text)
(OUT_DIR / "phase3_4_holdout_summary.txt").write_text(text + "\n")
