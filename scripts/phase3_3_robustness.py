"""Phase 3.3 — Robustness / validation sprint for Combo1 vs A (and F).

This script does NOT change any strategy. It only consumes the artifacts
already produced by `scripts/build_improvement_artifacts.py` and runs four
robustness tests:

- Rb1 — fixed comparator-set rank composite (A, F, Combo1; and a 5-variant set)
- Rb2 — raw-metric composite (z-score normalized, same economic weights as prod score)
- Rb3 — block bootstrap on weekly net returns (Sharpe, return, max DD)
- Rb4 — subperiod / holdout-style split (halves) on the weekly net returns

Outputs a single JSON summary next to a small markdown-friendly report.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
OUT_DIR = ROOT / "docs" / "research" / "phase3_3_artifacts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


A_NAME = "improved_phase2b_regime_confidence_boost"
F_NAME = "improved_phase2b_combo_abc"
C_NAME = "improved_phase3_1_combo_c1a_a1g"

# Optional 2 extra well-known reference baselines for a slightly wider fixed set
EXTRA_REF = ["baseline_hrp_default", "improved_phase3_1_c1_widened"]

# ---------- load static metrics ----------
cmp_df = pd.read_csv(L3_DIR / "portfolio_version_comparison.csv")

metrics_cols = [
    "ann_return",
    "ann_vol",
    "sharpe",
    "max_drawdown",
    "calmar",
    "cvar_5",
    "hit_rate",
    "avg_weekly_turnover",
    "annual_turnover",
    "avg_bil_weight",
    "avg_spy_weight",
    "avg_cash_weight",
    "upside_capture_positive_weeks",
    "downside_capture_negative_weeks",
    "recovery_week_capture",
    "recovery_fragile_capture",
    "recovery_confirmed_capture",
    "calm_week_capture",
    "stress_downside_capture",
    "production_score",
]

wanted_rows = [A_NAME, F_NAME, C_NAME] + EXTRA_REF
sub = cmp_df.set_index("version_name").loc[wanted_rows, metrics_cols]


def rank_pct(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Replicates scripts/build_improvement_artifacts.py rank_score."""
    s = pd.Series(series, dtype=float)
    if not higher_is_better:
        s = -s
    return s.rank(pct=True, method="average")


def prod_composite(df: pd.DataFrame) -> pd.Series:
    """Same rank-based production composite used by the dashboard."""
    return (
        0.22 * rank_pct(df["sharpe"], True)
        + 0.16 * rank_pct(df["calmar"], True)
        + 0.14 * rank_pct(df["max_drawdown"].abs(), False)
        + 0.10 * rank_pct(df["cvar_5"].abs(), False)
        + 0.12 * rank_pct(df["upside_capture_positive_weeks"], True)
        + 0.10 * rank_pct(df["recovery_week_capture"], True)
        + 0.08 * rank_pct(df["avg_cash_weight"], False)
        + 0.08 * rank_pct(df["avg_weekly_turnover"], False)
    )


# =========================================================================
# Rb1 — fixed comparator set
# =========================================================================

rb1_results = {}

# Minimal 3-variant set
min_set = sub.loc[[A_NAME, F_NAME, C_NAME]].copy()
min_set["prod_composite_fixed3"] = prod_composite(min_set)
rb1_results["fixed_3"] = min_set[["prod_composite_fixed3"]].to_dict()["prod_composite_fixed3"]
rb1_results["fixed_3_delta_combo1_vs_A"] = float(
    min_set.loc[C_NAME, "prod_composite_fixed3"] - min_set.loc[A_NAME, "prod_composite_fixed3"]
)
rb1_results["fixed_3_delta_combo1_vs_F"] = float(
    min_set.loc[C_NAME, "prod_composite_fixed3"] - min_set.loc[F_NAME, "prod_composite_fixed3"]
)

# 5-variant fixed set
five_set = sub.loc[[A_NAME, F_NAME, C_NAME] + EXTRA_REF].copy()
five_set["prod_composite_fixed5"] = prod_composite(five_set)
rb1_results["fixed_5"] = five_set[["prod_composite_fixed5"]].to_dict()["prod_composite_fixed5"]
rb1_results["fixed_5_delta_combo1_vs_A"] = float(
    five_set.loc[C_NAME, "prod_composite_fixed5"] - five_set.loc[A_NAME, "prod_composite_fixed5"]
)
rb1_results["fixed_5_delta_combo1_vs_F"] = float(
    five_set.loc[C_NAME, "prod_composite_fixed5"] - five_set.loc[F_NAME, "prod_composite_fixed5"]
)

# Full pool (as-built) for reference
full_pool = cmp_df.set_index("version_name")[metrics_cols].copy()
full_pool["prod_composite_full"] = prod_composite(full_pool)
rb1_results["full_pool"] = {
    A_NAME: float(full_pool.loc[A_NAME, "prod_composite_full"]),
    F_NAME: float(full_pool.loc[F_NAME, "prod_composite_full"]),
    C_NAME: float(full_pool.loc[C_NAME, "prod_composite_full"]),
}
rb1_results["full_pool_delta_combo1_vs_A"] = float(
    full_pool.loc[C_NAME, "prod_composite_full"] - full_pool.loc[A_NAME, "prod_composite_full"]
)


# =========================================================================
# Rb2 — raw-metric composite (z-score, not rank)
# =========================================================================

# Use a consistent comparator pool of full portfolio universe for means/sds
# so that z-scores are comparable and meaningful.  For the *score*, we use the
# same economic weights.
metric_direction = {
    "sharpe": +1,
    "calmar": +1,
    "max_drawdown": +1,          # sign flip below: we z-score the *absolute* DD and negate
    "cvar_5": +1,                # same treatment as DD (use |cvar|, negate)
    "upside_capture_positive_weeks": +1,
    "recovery_week_capture": +1,
    "avg_cash_weight": -1,       # lower is better
    "avg_weekly_turnover": -1,   # lower is better
}

# Weights identical to the production composite:
raw_weights = {
    "sharpe": 0.22,
    "calmar": 0.16,
    "max_drawdown": 0.14,
    "cvar_5": 0.10,
    "upside_capture_positive_weeks": 0.12,
    "recovery_week_capture": 0.10,
    "avg_cash_weight": 0.08,
    "avg_weekly_turnover": 0.08,
}


def zscore_col(series: pd.Series, use_abs: bool) -> pd.Series:
    v = series.abs() if use_abs else series
    mu = v.mean()
    sd = v.std(ddof=0)
    if sd == 0 or math.isnan(sd):
        return v * 0.0
    return (v - mu) / sd


raw_mat = pd.DataFrame(index=cmp_df["version_name"])
for col, w in raw_weights.items():
    use_abs = col in {"max_drawdown", "cvar_5"}
    z = zscore_col(cmp_df.set_index("version_name")[col], use_abs=use_abs)
    # For max_drawdown/cvar, the absolute value being larger is worse → flip sign
    if col in {"max_drawdown", "cvar_5"} or metric_direction[col] == -1:
        z = -z
    raw_mat[col + "_z"] = z * w

raw_mat["raw_composite"] = raw_mat.sum(axis=1)

rb2_results = {
    A_NAME: float(raw_mat.loc[A_NAME, "raw_composite"]),
    F_NAME: float(raw_mat.loc[F_NAME, "raw_composite"]),
    C_NAME: float(raw_mat.loc[C_NAME, "raw_composite"]),
}
rb2_results["delta_combo1_vs_A"] = rb2_results[C_NAME] - rb2_results[A_NAME]
rb2_results["delta_combo1_vs_F"] = rb2_results[C_NAME] - rb2_results[F_NAME]

# Also output the per-metric breakdown for A, F, Combo1
rb2_results["breakdown"] = raw_mat.loc[[A_NAME, F_NAME, C_NAME]].to_dict(orient="index")


# =========================================================================
# Rb3 — block bootstrap on weekly net returns
# =========================================================================


def read_net_returns(version_name: str) -> pd.Series:
    fp = L3_DIR / f"portfolio_version_returns_{version_name}.csv"
    df = pd.read_csv(fp, index_col=0, parse_dates=True)
    s = df["net_return"].astype(float)
    s.name = version_name
    return s


ret_a = read_net_returns(A_NAME)
ret_f = read_net_returns(F_NAME)
ret_c = read_net_returns(C_NAME)

# Align on common index and drop the warm-up "all zero" rows for cleanliness
rets = pd.concat([ret_a, ret_f, ret_c], axis=1).dropna()
# Use active period: first index with any non-zero value in any column
active_start = rets[(rets != 0).any(axis=1)].index.min()
rets = rets.loc[active_start:]


def sharpe_annualized(r: pd.Series) -> float:
    r = r.dropna()
    if r.std(ddof=0) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=0) * math.sqrt(52))


def annret(r: pd.Series) -> float:
    # geometric
    w = (1.0 + r).prod()
    n = len(r)
    if n <= 0:
        return 0.0
    return float(w ** (52.0 / n) - 1.0)


def maxdd_from(r: pd.Series) -> float:
    wealth = (1.0 + r).cumprod()
    roll_max = wealth.cummax()
    dd = wealth / roll_max - 1.0
    return float(dd.min())


def cvar5(r: pd.Series) -> float:
    q = r.quantile(0.05)
    tail = r[r <= q]
    if len(tail) == 0:
        return 0.0
    return float(tail.mean())


def block_bootstrap_indices(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(math.ceil(n / block_len))
    starts = rng.integers(low=0, high=max(1, n - block_len + 1), size=n_blocks)
    idx = np.concatenate([np.arange(s, s + block_len) for s in starts])[:n]
    return idx


def bootstrap_diff(
    r_target: pd.Series,
    r_base: pd.Series,
    stat_fn,
    n_iter: int = 2000,
    block_len: int = 13,
    seed: int = 20260418,
) -> dict:
    rng = np.random.default_rng(seed)
    n = len(r_target)
    diffs = np.empty(n_iter, dtype=float)
    vals_target = np.empty(n_iter, dtype=float)
    vals_base = np.empty(n_iter, dtype=float)
    r_t_vals = r_target.values
    r_b_vals = r_base.values
    for i in range(n_iter):
        idx = block_bootstrap_indices(n, block_len, rng)
        rt = pd.Series(r_t_vals[idx])
        rb = pd.Series(r_b_vals[idx])
        v_t = stat_fn(rt)
        v_b = stat_fn(rb)
        vals_target[i] = v_t
        vals_base[i] = v_b
        diffs[i] = v_t - v_b
    return {
        "mean_target": float(np.mean(vals_target)),
        "mean_base": float(np.mean(vals_base)),
        "mean_diff": float(np.mean(diffs)),
        "median_diff": float(np.median(diffs)),
        "std_diff": float(np.std(diffs)),
        "p_target_beats_base": float(np.mean(diffs > 0)),
        "ci_2_5": float(np.quantile(diffs, 0.025)),
        "ci_97_5": float(np.quantile(diffs, 0.975)),
    }


rb3_results = {}
for stat_name, stat_fn in [
    ("sharpe", sharpe_annualized),
    ("ann_return", annret),
    ("max_drawdown", maxdd_from),
    ("cvar5", cvar5),
]:
    rb3_results[f"{stat_name}_combo1_vs_A"] = bootstrap_diff(
        rets[C_NAME], rets[A_NAME], stat_fn, n_iter=2000, block_len=13, seed=20260418,
    )
    rb3_results[f"{stat_name}_combo1_vs_F"] = bootstrap_diff(
        rets[C_NAME], rets[F_NAME], stat_fn, n_iter=2000, block_len=13, seed=20260418,
    )

rb3_results["n_weeks"] = len(rets)
rb3_results["date_min"] = str(rets.index.min().date())
rb3_results["date_max"] = str(rets.index.max().date())
rb3_results["block_len_weeks"] = 13
rb3_results["n_iter"] = 2000


# =========================================================================
# Rb4 — subperiod / holdout-style split
# =========================================================================

# Strategy tuning in this repo covered most of the available history, so a
# true unseen holdout is not possible. Instead we split the active series at
# two points that partition the sample into sensibly-large regimes-spanning
# halves and report each subperiod independently.

split_points = [
    ("calendar_mid", pd.Timestamp("2015-12-31")),
    ("half_length", rets.index[len(rets) // 2]),
]

rb4_results = {}
for label, cut in split_points:
    pre = rets.loc[:cut]
    post = rets.loc[cut + pd.Timedelta(days=1):]
    block = {}
    for name, r in [("pre", pre), ("post", post)]:
        block[name] = {
            "n_weeks": int(len(r)),
            "date_min": str(r.index.min().date()) if len(r) else None,
            "date_max": str(r.index.max().date()) if len(r) else None,
            "A_sharpe": sharpe_annualized(r[A_NAME]),
            "F_sharpe": sharpe_annualized(r[F_NAME]),
            "C_sharpe": sharpe_annualized(r[C_NAME]),
            "A_ann_return": annret(r[A_NAME]),
            "F_ann_return": annret(r[F_NAME]),
            "C_ann_return": annret(r[C_NAME]),
            "A_max_dd": maxdd_from(r[A_NAME]),
            "F_max_dd": maxdd_from(r[F_NAME]),
            "C_max_dd": maxdd_from(r[C_NAME]),
            "A_cvar5": cvar5(r[A_NAME]),
            "F_cvar5": cvar5(r[F_NAME]),
            "C_cvar5": cvar5(r[C_NAME]),
            "combo1_sharpe_minus_A": sharpe_annualized(r[C_NAME]) - sharpe_annualized(r[A_NAME]),
            "combo1_sharpe_minus_F": sharpe_annualized(r[C_NAME]) - sharpe_annualized(r[F_NAME]),
            "combo1_ret_minus_A": annret(r[C_NAME]) - annret(r[A_NAME]),
            "combo1_dd_minus_A": maxdd_from(r[C_NAME]) - maxdd_from(r[A_NAME]),
        }
    rb4_results[label] = {"cut": str(pd.Timestamp(cut).date()), "blocks": block}

# A quick rolling-Sharpe diff series — extra diagnostic (every 104-week window)
roll_window = 104
ra = rets[A_NAME]
rc = rets[C_NAME]


def rolling_sharpe(r: pd.Series, w: int) -> pd.Series:
    mu = r.rolling(w).mean()
    sd = r.rolling(w).std(ddof=0)
    return (mu / sd.replace(0, np.nan)) * math.sqrt(52)


sh_a = rolling_sharpe(ra, roll_window)
sh_c = rolling_sharpe(rc, roll_window)
diff = (sh_c - sh_a).dropna()
rb4_results["rolling_sharpe_diff_104w"] = {
    "window_weeks": roll_window,
    "mean_diff": float(diff.mean()),
    "median_diff": float(diff.median()),
    "fraction_windows_combo1_beats_A": float((diff > 0).mean()),
    "min_diff": float(diff.min()),
    "max_diff": float(diff.max()),
}


# =========================================================================
# Save artifacts
# =========================================================================


def _jsonify(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    raise TypeError(f"Unhandled type {type(o)}")


out = {
    "versions": {
        "A": A_NAME,
        "F": F_NAME,
        "Combo1": C_NAME,
    },
    "core_metrics_snapshot": sub.to_dict(orient="index"),
    "Rb1_fixed_comparator_set": rb1_results,
    "Rb2_raw_metric_composite": rb2_results,
    "Rb3_block_bootstrap": rb3_results,
    "Rb4_subperiod_holdout": rb4_results,
}

with (OUT_DIR / "phase3_3_results.json").open("w") as f:
    json.dump(out, f, indent=2, default=_jsonify)

# quick textual summary
lines = []
lines.append("=== Phase 3.3 — Robustness summary ===\n")

lines.append("Rb1 (rank composite, fixed comparator sets):")
lines.append(f"  Full pool  — A={rb1_results['full_pool'][A_NAME]:.4f}  "
             f"F={rb1_results['full_pool'][F_NAME]:.4f}  "
             f"Combo1={rb1_results['full_pool'][C_NAME]:.4f}  "
             f"Δ(Combo1-A)={rb1_results['full_pool_delta_combo1_vs_A']:+.4f}")
lines.append(f"  Fixed 3   — A={rb1_results['fixed_3'][A_NAME]:.4f}  "
             f"F={rb1_results['fixed_3'][F_NAME]:.4f}  "
             f"Combo1={rb1_results['fixed_3'][C_NAME]:.4f}  "
             f"Δ(Combo1-A)={rb1_results['fixed_3_delta_combo1_vs_A']:+.4f}")
lines.append(f"  Fixed 5   — A={rb1_results['fixed_5'][A_NAME]:.4f}  "
             f"F={rb1_results['fixed_5'][F_NAME]:.4f}  "
             f"Combo1={rb1_results['fixed_5'][C_NAME]:.4f}  "
             f"Δ(Combo1-A)={rb1_results['fixed_5_delta_combo1_vs_A']:+.4f}")
lines.append("")

lines.append("Rb2 (raw-metric z-score composite, same weights):")
lines.append(f"  A      = {rb2_results[A_NAME]:+.4f}")
lines.append(f"  F      = {rb2_results[F_NAME]:+.4f}")
lines.append(f"  Combo1 = {rb2_results[C_NAME]:+.4f}")
lines.append(f"  Δ(Combo1-A) = {rb2_results['delta_combo1_vs_A']:+.4f}")
lines.append(f"  Δ(Combo1-F) = {rb2_results['delta_combo1_vs_F']:+.4f}")
lines.append("")

lines.append("Rb3 (13-week block bootstrap, 2000 iters):")
for k, v in rb3_results.items():
    if isinstance(v, dict):
        lines.append(
            f"  {k:30s} mean_diff={v['mean_diff']:+.4f}  "
            f"CI95=[{v['ci_2_5']:+.4f},{v['ci_97_5']:+.4f}]  "
            f"P(target>base)={v['p_target_beats_base']:.3f}"
        )
lines.append("")

lines.append("Rb4 (subperiod halves):")
for label, info in rb4_results.items():
    if label == "rolling_sharpe_diff_104w":
        rs = info
        lines.append(
            f"  rolling 104w Sharpe(Combo1) - Sharpe(A):  mean={rs['mean_diff']:+.4f}  "
            f"median={rs['median_diff']:+.4f}  frac_windows>0={rs['fraction_windows_combo1_beats_A']:.3f}  "
            f"min={rs['min_diff']:+.4f} max={rs['max_diff']:+.4f}"
        )
        continue
    lines.append(f"  split '{label}' at {info['cut']}:")
    for half, d in info["blocks"].items():
        lines.append(
            f"    {half:5s} n={d['n_weeks']:4d}  A_sh={d['A_sharpe']:.3f}  "
            f"F_sh={d['F_sharpe']:.3f}  C_sh={d['C_sharpe']:.3f}  "
            f"Δ(C-A)={d['combo1_sharpe_minus_A']:+.3f}  "
            f"Δ(C-F)={d['combo1_sharpe_minus_F']:+.3f}  "
            f"C-A_ret={d['combo1_ret_minus_A']:+.4f}  "
            f"C-A_dd={d['combo1_dd_minus_A']:+.4f}"
        )

text = "\n".join(lines)
print(text)
(OUT_DIR / "phase3_3_summary.txt").write_text(text + "\n")
