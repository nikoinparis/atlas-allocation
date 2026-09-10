"""Layer 6 — Allocator Benchmark & Optimizer Audit.

Tests whether the candidate (Phase Z / BB / Phase CC surrogate) and the
production allocator actually beat simple, mature portfolio-construction
baselines under the same data, date range, costs, and constraints.

External libraries (skfolio, riskfolio-lib, pypfopt, vectorbt) are NOT
installed in this environment, and web egress to GitHub for direct repo
inspection was BLOCKED. All baselines are therefore implemented as
lightweight, internal numpy/pandas/scipy versions of well-documented
algorithms (EW, IV, HRP single-linkage / bisection, ERC by inverse-vol
seed + iterative scaling). No external code is copied.

The allocators run on the project's existing 7-sleeve panel of
already-saved sleeve-level strategy net returns (not on raw ETF returns).
Comparison is sleeve-level only. The original production and candidate
portfolio_version_returns_*.csv files are used unchanged for the
"current production" and "current candidate" rows.

Outputs:
  reports/allocator_benchmark/{candidate}_allocator_benchmark.md
  data/research/allocator_benchmark/{candidate}_allocator_comparison.csv
  data/research/allocator_benchmark/{candidate}_risk_contribution.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PANEL_7 = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
    "composite_structural_defense_sleeve",
]
TRAIN_WINDOW = 156
REBAL_FREQ_WEEKS = 4
MAX_W = 0.45


def autoselect_candidate() -> str:
    for prefix in ["improved_phasebb_", "improved_phaseaa_", "improved_phasez_"]:
        files = sorted(roc.LAYER3_DIR.glob(f"portfolio_version_returns_{prefix}*.csv"))
        if files:
            return files[-1].stem.replace("portfolio_version_returns_", "")
    return roc.PHASEZ_Z1


def load_sleeve_panel(panel: list[str]) -> pd.DataFrame:
    rows = {}
    for s in panel:
        p = roc.LAYER2A_DIR / f"strategy_returns_{s}.csv"
        if p.exists():
            df = pd.read_csv(p, index_col=0, parse_dates=True)
            rows[s] = df["net_return"].astype(float)
    return pd.DataFrame(rows).dropna(how="all").sort_index()


# --------------------------------------------------------------------------
# allocators (internal)
# --------------------------------------------------------------------------

def cap_normalize(w: pd.Series, cap: float = MAX_W) -> pd.Series:
    w = w.clip(lower=0).fillna(0.0)
    if w.sum() <= 0:
        return pd.Series(1.0 / len(w), index=w.index)
    w = w / w.sum()
    for _ in range(20):
        over = w > cap
        if not over.any():
            break
        excess = (w[over] - cap).sum()
        w[over] = cap
        under = w < cap - 1e-12
        if under.any() and excess > 0:
            w[under] += excess * w[under] / w[under].sum()
        elif excess > 0:
            w += excess / len(w)
        w = w.clip(lower=0)
        w = w / w.sum()
    return w / w.sum()


def alloc_equal_weight(cov: pd.DataFrame) -> pd.Series:
    n = len(cov)
    return cap_normalize(pd.Series(1.0/n, index=cov.index))


def alloc_inverse_vol(cov: pd.DataFrame) -> pd.Series:
    vol = pd.Series(np.sqrt(np.diag(cov.values)), index=cov.index)
    inv = 1.0 / vol.replace(0, np.nan).clip(lower=1e-12)
    return cap_normalize(inv.fillna(inv.median()).fillna(1.0))


def alloc_max_diversification(cov: pd.DataFrame) -> pd.Series:
    """Choo & Choueifaty Most-Diversified Portfolio approximation:
    weight ∝ 1/vol (inverse-vol) penalised by row-correlation. Lightweight
    closed-form approximation; not the full QP solution."""
    vol = np.sqrt(np.diag(cov.values))
    if (vol == 0).any():
        return alloc_inverse_vol(cov)
    corr = cov.values / np.outer(vol, vol)
    # diversification ratio numerator ≈ 1/vol; denominator ≈ row-mean correlation
    row_corr = corr.mean(axis=1).clip(min=1e-6)
    raw = (1.0 / vol) / row_corr
    return cap_normalize(pd.Series(raw, index=cov.index))


def alloc_erc(cov: pd.DataFrame, max_iter: int = 100, tol: float = 1e-6) -> pd.Series:
    """Equal Risk Contribution by iterative scaling from inverse-vol seed."""
    n = cov.shape[0]
    if n == 1:
        return pd.Series([1.0], index=cov.index)
    w = alloc_inverse_vol(cov).values
    w = w / w.sum()
    Sigma = cov.values
    for _ in range(max_iter):
        port_var = float(w @ Sigma @ w)
        marg = Sigma @ w
        rc = w * marg
        target = port_var / n
        # gradient step
        update = w * (target / np.maximum(rc, 1e-12)) ** 0.5
        update = update / update.sum()
        if np.max(np.abs(update - w)) < tol:
            w = update
            break
        w = update
    return cap_normalize(pd.Series(w, index=cov.index))


def alloc_hrp(cov: pd.DataFrame) -> pd.Series:
    """HRP: single-linkage on correlation distance + recursive bisection."""
    n = cov.shape[0]
    if n < 2:
        return alloc_inverse_vol(cov)
    vol = np.sqrt(np.diag(cov.values))
    if (vol == 0).any():
        return alloc_inverse_vol(cov)
    corr = cov.values / np.outer(vol, vol)
    np.fill_diagonal(corr, 1.0)
    corr = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    cond = squareform(dist, checks=False)
    if not np.isfinite(cond).all():
        return alloc_inverse_vol(cov)
    link = linkage(cond, method="single")
    ordered = list(cov.index[leaves_list(link)])
    w = pd.Series(1.0, index=ordered)
    clusters = [ordered]
    while clusters:
        c = clusters.pop(0)
        if len(c) <= 1:
            continue
        split = len(c) // 2
        left, right = c[:split], c[split:]
        # cluster variance via inverse-vol
        def cvar(members):
            sub = cov.loc[members, members]
            v = np.sqrt(np.diag(sub.values))
            if (v == 0).any(): return 1e-12
            iw = 1.0 / v
            iw = iw / iw.sum()
            return float(iw @ sub.values @ iw)
        lvar = cvar(left); rvar = cvar(right)
        alpha = 1.0 - lvar / max(lvar + rvar, 1e-12)
        w[left] *= alpha
        w[right] *= 1 - alpha
        clusters.extend([left, right])
    return cap_normalize(w.reindex(cov.index).fillna(0.0))


def alloc_benchmark_tracker(cov: pd.DataFrame, panel: pd.DataFrame) -> pd.Series:
    """Simplest possible 'benchmark tracker' baseline: weight ∝ 1/n on
    sleeves whose 12-month rolling Sharpe is in the top half. Not a
    fitted-tracker; used only as a sanity baseline."""
    # use most recent 52-week Sharpe as score
    score = panel.tail(52).mean() / panel.tail(52).std(ddof=0).replace(0, np.nan)
    score = score.replace([np.inf, -np.inf], np.nan).fillna(score.median()).fillna(0)
    median = score.median()
    keep = score[score >= median].index.tolist()
    if not keep:
        return alloc_equal_weight(cov)
    w = pd.Series(0.0, index=cov.index)
    w[keep] = 1.0 / len(keep)
    return cap_normalize(w)


ALLOCATORS = {
    "equal_weight": alloc_equal_weight,
    "inverse_vol": alloc_inverse_vol,
    "erc_internal": alloc_erc,
    "max_diversification_lite": alloc_max_diversification,
    "hrp_internal": alloc_hrp,
    "benchmark_tracker_lite": lambda cov: alloc_benchmark_tracker(cov, _panel_for_tracker),
}


_panel_for_tracker: pd.DataFrame | None = None  # set in main


def backtest_allocator(panel: pd.DataFrame, alloc_fn, halfspread: float = roc.DEFAULT_HALFSPREAD) -> pd.DataFrame:
    """Run a monthly-rebalance backtest of one allocator on the sleeve panel."""
    dates = panel.index
    weights = pd.DataFrame(0.0, index=dates, columns=panel.columns)
    last_w = pd.Series(0.0, index=panel.columns)
    for i, d in enumerate(dates):
        if i == 0 or (i % REBAL_FREQ_WEEKS == 0 and i >= TRAIN_WINDOW):
            train = panel.iloc[max(0, i - TRAIN_WINDOW):i].dropna(how="any")
            if len(train) >= 26 and train.shape[1] >= 2:
                cov = train.cov()
                last_w = alloc_fn(cov).reindex(panel.columns).fillna(0.0)
        weights.iloc[i] = last_w
    next_r = panel.shift(-1)
    common = weights.index.intersection(next_r.index)
    gross = (weights.loc[common] * next_r.loc[common].fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * halfspread
    net = gross - cost
    return pd.DataFrame({"gross": gross, "net": net, "turnover": turnover.reindex(common).fillna(0.0), "weights": weights.reindex(common).apply(lambda r: r.to_dict(), axis=1)}).reset_index().rename(columns={"index": "date"})


def metrics_from_net(net: pd.Series, turnover: pd.Series | None = None) -> dict:
    m = roc.metric_block(net)
    if turnover is not None:
        m["avg_turnover"] = float(turnover.mean())
        m["cost_drag_ann"] = float(turnover.mean() * roc.DEFAULT_HALFSPREAD * roc.WEEKS_PER_YEAR)
    return m


def risk_contribution(weights: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Average sleeve-level risk contribution over the backtest."""
    cov = panel.cov().values
    cols = panel.columns
    rows = []
    for c in cols:
        idx = list(cols).index(c)
        # average weight
        avg_w = float(weights[c].mean()) if c in weights.columns else 0.0
        # marginal contribution to portfolio variance using average weights
        avg = weights[cols].mean().values
        sigma_w = cov @ avg
        port_var = float(avg @ cov @ avg)
        if port_var <= 0:
            rc = 0.0; rc_pct = 0.0
        else:
            rc = float(avg[idx] * sigma_w[idx])
            rc_pct = rc / port_var
        rows.append({
            "sleeve": c,
            "avg_dollar_weight": avg_w,
            "avg_risk_contribution": rc,
            "risk_contribution_pct": rc_pct,
            "risk_minus_dollar_weight_pct": rc_pct - avg_w,
        })
    return pd.DataFrame(rows).sort_values("risk_contribution_pct", ascending=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", nargs="?", default=None)
    parser.add_argument("--quick", action="store_true", help="Quick screen — runs only EW, IV, HRP baselines (skips ERC, MaxDiv, tracker).")
    args = parser.parse_args()
    if args.quick:
        global ALLOCATORS
        ALLOCATORS = {k: v for k, v in ALLOCATORS.items() if k in ("equal_weight", "inverse_vol", "hrp_internal")}
    candidate = args.candidate or autoselect_candidate()
    baseline = roc.PRODUCTION_PIN
    print(f"Allocator benchmark: candidate={candidate}, baseline={baseline}")

    print("Loading sleeve panel...")
    panel = load_sleeve_panel(PANEL_7).dropna(how="any")
    print(f"Sleeve panel shape: {panel.shape}")

    global _panel_for_tracker
    _panel_for_tracker = panel

    rows = []

    # Run internal allocator baselines
    for alloc_name, fn in ALLOCATORS.items():
        print(f"  running {alloc_name}...")
        bt = backtest_allocator(panel, fn)
        net = bt["net"].dropna()
        turn = bt["turnover"]
        m = metrics_from_net(net, turn)
        rows.append({"allocator": alloc_name, **m})

    # Production
    pdr = roc.load_portfolio_returns(baseline)
    if pdr is not None:
        m = roc.metric_block(pdr["net_return"].dropna())
        m["avg_turnover"] = float(pdr["turnover"].mean()) if "turnover" in pdr.columns else float("nan")
        m["cost_drag_ann"] = m["avg_turnover"] * roc.DEFAULT_HALFSPREAD * roc.WEEKS_PER_YEAR if pd.notna(m["avg_turnover"]) else float("nan")
        rows.append({"allocator": f"production:{baseline}", **m})

    # Candidate
    cdr = roc.load_portfolio_returns(candidate)
    if cdr is not None:
        m = roc.metric_block(cdr["net_return"].dropna())
        m["avg_turnover"] = float(cdr["turnover"].mean()) if "turnover" in cdr.columns else float("nan")
        m["cost_drag_ann"] = m["avg_turnover"] * roc.DEFAULT_HALFSPREAD * roc.WEEKS_PER_YEAR if pd.notna(m["avg_turnover"]) else float("nan")
        rows.append({"allocator": f"candidate:{candidate}", **m})

    comp = pd.DataFrame(rows)
    comp_csv = roc.ROOT / "data" / "research" / "allocator_benchmark" / f"{candidate}_allocator_comparison.csv"
    comp_csv.parent.mkdir(parents=True, exist_ok=True)
    comp.to_csv(comp_csv, index=False)

    # Risk contribution
    cw = roc.load_portfolio_sleeve_weights(candidate)
    rc_df = pd.DataFrame()
    if cw is not None:
        cw_panel_only = cw[[c for c in PANEL_7 if c in cw.columns]]
        if cw_panel_only.shape[1] >= 2:
            rc_df = risk_contribution(cw_panel_only, panel[cw_panel_only.columns].reindex(cw_panel_only.index).dropna(how="any"))
        else:
            print(f"  candidate sleeve schema does not match PANEL_7 — risk contribution skipped (cols={list(cw.columns)})")
    rc_csv = roc.ROOT / "data" / "research" / "allocator_benchmark" / f"{candidate}_risk_contribution.csv"
    rc_csv.parent.mkdir(parents=True, exist_ok=True)
    if not rc_df.empty:
        rc_df.to_csv(rc_csv, index=False)

    # ----- Report -----
    rep = [f"# Allocator Benchmark Audit — {candidate}\n\n"]
    rep.append(f"**Production:** `{baseline}`\n\n")
    rep.append(f"**Sleeve panel:** {len(PANEL_7)} sleeves; {panel.shape[0]} weeks; {panel.index.min().date()} → {panel.index.max().date()}.\n\n")
    rep.append("**Allocators tested (internal implementations):**\n")
    rep.append("- equal_weight, inverse_vol, ERC (iterative), max_diversification (lightweight), HRP (single-linkage + bisection), benchmark_tracker (52w Sharpe top-half).\n")
    rep.append("- All run on the same 7-sleeve panel with the same 156w training window, monthly rebalance, 5bp half-spread cost, long-only, max sleeve weight 0.45.\n")
    rep.append("- External libs (skfolio, riskfolio-lib, pypfopt, vectorbt) NOT installed; web egress to GitHub for repo inspection BLOCKED. No external code is copied.\n\n")

    rep.append("## Allocator Comparison\n\n")
    rep.append("```\n" + comp.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    if not rc_df.empty:
        rep.append(f"## Risk Contribution — {candidate}\n\n")
        rep.append("```\n" + rc_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")
        # flag concentration
        flag = rc_df[rc_df["risk_minus_dollar_weight_pct"] > 0.10]
        if not flag.empty:
            rep.append("**Hidden concentration flagged:**\n")
            for _, r in flag.iterrows():
                rep.append(f"- `{r['sleeve']}`: dollar weight {r['avg_dollar_weight']*100:.1f}% but risk contribution {r['risk_contribution_pct']*100:.1f}% (delta {r['risk_minus_dollar_weight_pct']*100:+.1f}pp).\n")
            rep.append("\n")
    else:
        rep.append(roc.warn_section(f"Sleeve weights file for `{candidate}` not available; risk contribution skipped."))

    # Baseline challenge
    rep.append("## Baseline Challenge\n\n")
    if cdr is not None:
        cand_sh = roc.sharpe(cdr["net_return"].dropna())
        cand_ret = roc.annualised_return(cdr["net_return"].dropna())
        cand_dd = roc.max_drawdown(cdr["net_return"].dropna())
    else:
        cand_sh = cand_ret = cand_dd = float("nan")
    if pdr is not None:
        prod_sh = roc.sharpe(pdr["net_return"].dropna())
        prod_ret = roc.annualised_return(pdr["net_return"].dropna())
    else:
        prod_sh = prod_ret = float("nan")
    by_alloc = comp.set_index("allocator")
    questions = []
    for label, key in [("Equal Weight", "equal_weight"), ("Inverse Vol", "inverse_vol"),
                       ("ERC (internal)", "erc_internal"), ("HRP (internal)", "hrp_internal"),
                       ("Max Diversification (lite)", "max_diversification_lite")]:
        if key not in by_alloc.index:
            continue
        ar = float(by_alloc.at[key, "ann_return"])
        sh = float(by_alloc.at[key, "sharpe"])
        beat_ret = cand_ret > ar if pd.notna(cand_ret) else False
        beat_sh = cand_sh > sh if pd.notna(cand_sh) else False
        questions.append(f"- Does the candidate beat **{label}** on annualised return? **{'YES' if beat_ret else 'NO'}** "
                         f"(cand {cand_ret*100:+.2f}% vs {label} {ar*100:+.2f}%); on Sharpe? **{'YES' if beat_sh else 'NO'}** "
                         f"(cand {cand_sh:.3f} vs {label} {sh:.3f}).")
    if pd.notna(cand_ret) and pd.notna(prod_ret):
        questions.append(f"- Does the candidate beat **production** on annualised return? **{'YES' if cand_ret > prod_ret else 'NO'}** "
                         f"(cand {cand_ret*100:+.2f}% vs prod {prod_ret*100:+.2f}%); on Sharpe? **{'YES' if cand_sh > prod_sh else 'NO'}**.")
    rep.extend([q + "\n" for q in questions])
    rep.append("\n")
    # complexity verdict
    rep.append("**Is the extra complexity justified?**\n\n")
    simple_max_sh = float(by_alloc.loc[["equal_weight", "inverse_vol"]]["sharpe"].max())
    if pd.notna(cand_sh) and cand_sh > simple_max_sh + 0.05:
        rep.append("YES — candidate Sharpe exceeds the best simple baseline (Equal Weight / Inverse Vol) by more than 0.05.\n\n")
    else:
        rep.append("**NO / MARGINAL** — candidate Sharpe does not clearly exceed the best simple baseline by 0.05+. "
                   "Extra complexity may not be earning its keep on Sharpe; consider whether the candidate's edge is on max drawdown, "
                   "CVaR, or state-by-state defense rather than headline Sharpe.\n\n")

    rep.append("## Promotion-readiness sign-off\n\n")
    if pd.notna(cand_ret) and pd.notna(prod_ret) and cand_ret > prod_ret and pd.notna(cand_sh) and cand_sh > simple_max_sh + 0.05:
        rep.append("Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. **Allocator-side bar passed.**\n\n")
    else:
        rep.append("Candidate does NOT beat production on annualised return OR does NOT clearly beat the best simple baseline on Sharpe. **Allocator-side bar NOT passed for production promotion.**\n\n")

    out_path = roc.REPORTS_DIR / "allocator_benchmark" / f"{candidate}_allocator_benchmark.md"
    out_path.write_text("".join(rep))
    print(f"Wrote {out_path}")
    print(f"Wrote {comp_csv}")
    if not rc_df.empty:
        print(f"Wrote {rc_csv}")


if __name__ == "__main__":
    main()
