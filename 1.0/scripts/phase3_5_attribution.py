"""Phase 3.5 — attribution of Combo1 into its two halves.

Isolate:
  - H1 = A1g-only (state-gated sector sleeve, NO widened tilt)
      → improved_phase3_1_a1_state_gated
  - H2 = C1a-only (widened state-leader tilt, NO sector sleeve)
      → improved_phase3_1_c1_widened
  - H3 = Combo1 (reference)
      → improved_phase3_1_combo_c1a_a1g

and evaluate each under the Phase 3.4 holdout discipline:
  * full-history / pre-holdout / holdout windows
  * deltas vs A, F, and Combo1 in each window
  * 13-week block bootstrap vs A on holdout (same seed convention)
  * 13-week block bootstrap vs Combo1 on holdout (to test whether either
    half explains Combo1's edge or its holdout failure)

All sprint artifacts written to docs/research/phase3_5_artifacts/.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
OUT_DIR = ROOT / "docs" / "research" / "phase3_5_artifacts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Reuse the Phase 3.4 pre-declared holdout window unchanged.
HOLDOUT_START = pd.Timestamp("2024-04-19")

A_NAME = "improved_phase2b_regime_confidence_boost"
F_NAME = "improved_phase2b_combo_abc"
H1_NAME = "improved_phase3_1_a1_state_gated"          # A1g-only
H2_NAME = "improved_phase3_1_c1_widened"              # C1a-only
H3_NAME = "improved_phase3_1_combo_c1a_a1g"           # Combo1

VERSIONS = [A_NAME, F_NAME, H1_NAME, H2_NAME, H3_NAME]

LABEL = {
    A_NAME: "A (production)",
    F_NAME: "F (shadow)",
    H1_NAME: "H1 (A1g-only)",
    H2_NAME: "H2 (C1a-only)",
    H3_NAME: "H3 (Combo1)",
}


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


# ---- load ----
series = {v: read_net_returns(v) for v in VERSIONS}
rets = pd.concat(series.values(), axis=1).dropna()
active_start = rets[(rets != 0).any(axis=1)].index.min()
rets = rets.loc[active_start:]

dev = rets.loc[:HOLDOUT_START - pd.Timedelta(days=1)]
hold = rets.loc[HOLDOUT_START:]


# ---- per-window metrics ----
window_blocks = {}
for window_name, window_df in [("full_history", rets), ("pre_holdout", dev), ("holdout", hold)]:
    block = {
        "date_min": str(window_df.index.min().date()) if len(window_df) else None,
        "date_max": str(window_df.index.max().date()) if len(window_df) else None,
        "n_weeks": int(len(window_df)),
        "versions": {v: metrics_block(window_df[v]) for v in VERSIONS},
    }
    window_blocks[window_name] = block


# ---- deltas vs A, F, Combo1 within each window ----
delta_tables = {}
for window_name, block in window_blocks.items():
    deltas = {}
    a = block["versions"][A_NAME]
    f = block["versions"][F_NAME]
    c = block["versions"][H3_NAME]
    for v in VERSIONS:
        m = block["versions"][v]
        deltas[v] = {
            "vs_A": {k: m[k] - a[k] for k in ("sharpe", "ann_return", "max_drawdown", "cvar_5", "calmar")},
            "vs_F": {k: m[k] - f[k] for k in ("sharpe", "ann_return", "max_drawdown", "cvar_5", "calmar")},
            "vs_Combo1": {k: m[k] - c[k] for k in ("sharpe", "ann_return", "max_drawdown", "cvar_5", "calmar")},
        }
    delta_tables[window_name] = deltas


# ---- block bootstrap ----
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


# Bootstrap vs A on each window for all candidates except A itself and F (F is baseline too).
# Also bootstrap vs Combo1 on holdout for H1 and H2 (to see if either half
# statistically dominates the combo on the 2-year holdout).
bootstrap_out = {}
for window_name, window_df in [("holdout", hold), ("pre_holdout", dev), ("full_history", rets)]:
    block = {}
    for v in (F_NAME, H1_NAME, H2_NAME, H3_NAME):
        block[f"{v}_sharpe_vs_A"]     = bootstrap_diff(window_df[v], window_df[A_NAME], sharpe_annualized)
        block[f"{v}_ann_return_vs_A"] = bootstrap_diff(window_df[v], window_df[A_NAME], annret)
        block[f"{v}_max_dd_vs_A"]     = bootstrap_diff(window_df[v], window_df[A_NAME], maxdd_from)
    # vs Combo1 (H3) — only meaningful for H1 and H2
    for v in (H1_NAME, H2_NAME):
        block[f"{v}_sharpe_vs_Combo1"]     = bootstrap_diff(window_df[v], window_df[H3_NAME], sharpe_annualized)
        block[f"{v}_ann_return_vs_Combo1"] = bootstrap_diff(window_df[v], window_df[H3_NAME], annret)
        block[f"{v}_max_dd_vs_Combo1"]     = bootstrap_diff(window_df[v], window_df[H3_NAME], maxdd_from)
    bootstrap_out[window_name] = block

payload = {
    "holdout_start": str(HOLDOUT_START.date()),
    "windows": window_blocks,
    "deltas": delta_tables,
    "bootstrap": bootstrap_out,
}

with (OUT_DIR / "phase3_5_attribution.json").open("w") as fh:
    json.dump(payload, fh, indent=2, default=str)


# ---- summary printout ----
lines = [f"Phase 3.5 attribution — holdout = {HOLDOUT_START.date()} onward"]
for window_name, block in window_blocks.items():
    lines.append(f"\n=== {window_name}  [{block['date_min']} .. {block['date_max']}]  n={block['n_weeks']} ===")
    lines.append(f"{'version':55s}  {'ann_ret':>9s}  {'ann_vol':>9s}  {'sharpe':>9s}  "
                 f"{'max_dd':>9s}  {'calmar':>9s}  {'cvar5':>9s}")
    for v in VERSIONS:
        m = block["versions"][v]
        lines.append(
            f"{LABEL[v]:55s}  {m['ann_return']:9.4f}  {m['ann_vol']:9.4f}  {m['sharpe']:9.3f}  "
            f"{m['max_drawdown']:9.4f}  {m['calmar']:9.3f}  {m['cvar_5']:9.4f}"
        )

for compare_label, compare_key in [("vs A", "vs_A"), ("vs F", "vs_F"), ("vs Combo1", "vs_Combo1")]:
    lines.append(f"\n=== Deltas {compare_label} (per window) ===")
    for window_name in ("full_history", "pre_holdout", "holdout"):
        lines.append(f"  window = {window_name}")
        dtbl = delta_tables[window_name]
        for v in VERSIONS:
            if compare_key == "vs_A" and v == A_NAME: continue
            if compare_key == "vs_F" and v == F_NAME: continue
            if compare_key == "vs_Combo1" and v == H3_NAME: continue
            d = dtbl[v][compare_key]
            lines.append(
                f"    {LABEL[v]:55s}  dSharpe={d['sharpe']:+.4f}  dRet={d['ann_return']:+.4f}  "
                f"dDD={d['max_drawdown']:+.4f}  dCvar={d['cvar_5']:+.4f}  dCalmar={d['calmar']:+.4f}"
            )

lines.append("\n=== Holdout block bootstrap vs A (13w blocks, 2000 iter) ===")
for key, res in bootstrap_out["holdout"].items():
    if "vs_A" not in key or "n" not in res:
        continue
    lines.append(
        f"  {key:60s}  n={res['n']:3d}  mean_d={res['mean_diff']:+.4f}  "
        f"CI95=[{res['ci_2_5']:+.4f},{res['ci_97_5']:+.4f}]  P(t>b)={res['p_target_beats_base']:.3f}"
    )

lines.append("\n=== Holdout block bootstrap vs Combo1 (H1, H2 only) ===")
for key, res in bootstrap_out["holdout"].items():
    if "vs_Combo1" not in key or "n" not in res:
        continue
    lines.append(
        f"  {key:60s}  n={res['n']:3d}  mean_d={res['mean_diff']:+.4f}  "
        f"CI95=[{res['ci_2_5']:+.4f},{res['ci_97_5']:+.4f}]  P(t>b)={res['p_target_beats_base']:.3f}"
    )

text = "\n".join(lines)
print(text)
(OUT_DIR / "phase3_5_attribution_summary.txt").write_text(text + "\n")
