"""Layer 5 — Robustness Simulation Audit.

Block bootstrap + worst-window analysis on the candidate's existing
net-return series. No re-execution of the strategy; this is a statistical
audit on already-saved returns.

Usage:
    python scripts/robustness_simulation_audit.py [candidate_name]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


N_SAMPLES = 1000
BLOCK_WEEKS = 26
WORST_WINDOWS = [13, 26, 52]


def autoselect_candidate() -> str:
    for prefix in ["improved_phasebb_", "improved_phaseaa_", "improved_phasez_"]:
        files = sorted(roc.LAYER3_DIR.glob(f"portfolio_version_returns_{prefix}*.csv"))
        if files:
            return files[-1].stem.replace("portfolio_version_returns_", "")
    return roc.PHASEZ_Z1


def worst_window(net: pd.Series, weeks: int) -> tuple[float, str, str]:
    if len(net) < weeks:
        return float("nan"), "", ""
    log_r = np.log1p(net.dropna())
    rolled = log_r.rolling(window=weeks).sum()
    if rolled.dropna().empty:
        return float("nan"), "", ""
    end = rolled.idxmin()
    start = log_r.index[log_r.index.get_indexer([end])[0] - weeks + 1]
    return float(np.expm1(rolled.loc[end])), str(start)[:10], str(end)[:10]


def stress_state_perf(net: pd.Series, state: pd.DataFrame) -> dict:
    df = pd.concat([net.rename("net"), state[["market_state"]]], axis=1).dropna()
    out = {}
    for s in ["stressed_panic", "recovery_fragile"]:
        sub = df[df["market_state"] == s]
        if len(sub):
            out[s] = {
                "n_weeks": int(len(sub)),
                "mean_wkly": float(sub["net"].mean()),
                "min_wkly": float(sub["net"].min()),
                "stress_state_sharpe_proxy": float(sub["net"].mean() / max(1e-12, sub["net"].std(ddof=0))),
            }
        else:
            out[s] = None
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", nargs="?", default=None)
    args = parser.parse_args()
    candidate = args.candidate or autoselect_candidate()
    baseline = roc.PRODUCTION_PIN
    print(f"Robustness audit: candidate={candidate}, baseline={baseline}")

    cd = roc.load_portfolio_returns(candidate)
    pd_ = roc.load_portfolio_returns(baseline)
    if cd is None or pd_ is None:
        print("ERROR: missing returns; aborting"); sys.exit(1)
    cn = cd["net_return"].dropna(); pn = pd_["net_return"].dropna()
    common = cn.index.intersection(pn.index)
    cn = cn.loc[common]; pn = pn.loc[common]

    out = [f"# Robustness Simulation Audit — {candidate}\n\n"]
    out.append(f"**Production baseline:** `{baseline}`\n\n")
    out.append(f"**Date range:** {common.min().date()} → {common.max().date()} ({len(common)} weeks)\n\n")
    out.append(f"**Bootstrap method:** moving-block bootstrap, block={BLOCK_WEEKS} weeks, samples={N_SAMPLES}.\n\n")

    if len(cn) < 4 * BLOCK_WEEKS:
        out.append(roc.warn_section(f"Return history short ({len(cn)} weeks). Bootstrap intervals may be wide."))

    # Bootstrap intervals
    metrics = {
        "ann_return": roc.annualised_return,
        "sharpe": roc.sharpe,
        "max_drawdown": roc.max_drawdown,
        "cvar_5": lambda s: roc.cvar(s, 0.05),
    }
    rows = []
    rng = np.random.default_rng(20260427)
    for label, series in [("candidate", cn), ("production", pn)]:
        for mname, fn in metrics.items():
            samples = roc.bootstrap_metric_distribution(series, fn=fn, n_samples=N_SAMPLES, block_weeks=BLOCK_WEEKS)
            lo, hi = roc.confidence_interval(samples, 0.05, 0.95)
            rows.append({
                "series": label,
                "metric": mname,
                "point_estimate": float(fn(series)),
                "ci_lo_5pct": lo,
                "ci_hi_95pct": hi,
                "n_samples": int(samples.size if samples.size else 0),
            })
    boot_df = pd.DataFrame(rows)
    out.append("## Bootstrap confidence intervals (90% CI, block=26w)\n\n")
    out.append("```\n" + boot_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")
    boot_csv = roc.ROOT / "data" / "research" / "backtest_realism" / f"{candidate}_block_bootstrap_summary.csv"
    boot_csv.parent.mkdir(parents=True, exist_ok=True)
    boot_df.to_csv(boot_csv, index=False)

    # Worst windows
    out.append("## Worst Rolling Windows\n\n")
    rows2 = []
    for w in WORST_WINDOWS:
        cval, cs, ce = worst_window(cn, w)
        pval, ps, pe = worst_window(pn, w)
        rows2.append({"window_weeks": w, "cand_worst": cval, "cand_start": cs, "cand_end": ce,
                      "prod_worst": pval, "prod_start": ps, "prod_end": pe,
                      "delta_cand_minus_prod": cval - pval if pd.notna(cval) and pd.notna(pval) else float("nan")})
    ww_df = pd.DataFrame(rows2)
    out.append("```\n" + ww_df.to_string(index=False, float_format=lambda x: f"{x*100:+.2f}%" if isinstance(x, float) else str(x)) + "\n```\n\n")

    # Stress-state performance
    try:
        state = roc.load_market_state(refined=False)
        stress_c = stress_state_perf(cn, state)
        stress_p = stress_state_perf(pn, state)
        out.append("## Stress-state-only performance\n\n")
        for s in stress_c:
            sc = stress_c[s]; sp = stress_p[s]
            if sc is None or sp is None:
                out.append(f"- `{s}`: insufficient state observations.\n")
                continue
            out.append(f"### {s}\n\n")
            out.append(f"- candidate: n={sc['n_weeks']}, mean wkly={sc['mean_wkly']:+.4f}, min wkly={sc['min_wkly']:+.4f}\n")
            out.append(f"- production: n={sp['n_weeks']}, mean wkly={sp['mean_wkly']:+.4f}, min wkly={sp['min_wkly']:+.4f}\n")
            out.append(f"- candidate vs production mean wkly delta: {(sc['mean_wkly']-sp['mean_wkly']):+.4f}\n\n")
    except Exception as e:
        out.append(roc.warn_section(f"Stress-state breakdown skipped: {e}"))

    # Doubled-cost sensitivity (rerun returns from weights if available; otherwise scale gross)
    cd_w = roc.load_portfolio_weights(candidate)
    pd_w = roc.load_portfolio_weights(baseline)
    if cd_w is not None and pd_w is not None and "turnover" in cd.columns:
        # Subtract one extra unit of cost (additional 5bp half-spread)
        extra = cd["turnover"].reindex(cn.index).fillna(0.0) * roc.DEFAULT_HALFSPREAD
        cn_doub = cn - extra
        extra_p = pd_["turnover"].reindex(pn.index).fillna(0.0) * roc.DEFAULT_HALFSPREAD
        pn_doub = pn - extra_p
        out.append("## Doubled-cost sensitivity\n\n")
        cm = roc.metric_block(cn_doub); pm = roc.metric_block(pn_doub)
        out.append(f"- candidate (doubled cost): ann return {cm['ann_return']*100:+.2f}%, Sharpe {cm['sharpe']:.3f}, MDD {cm['max_drawdown']*100:+.2f}%\n")
        out.append(f"- production (doubled cost): ann return {pm['ann_return']*100:+.2f}%, Sharpe {pm['sharpe']:.3f}, MDD {pm['max_drawdown']*100:+.2f}%\n")
        out.append(f"- delta ann return: {(cm['ann_return']-pm['ann_return'])*100:+.2f}pp\n\n")

    # Verdict
    out.append("## Robustness Verdict\n\n")
    cand_ar = roc.annualised_return(cn)
    prod_ar = roc.annualised_return(pn)
    cand_sh = roc.sharpe(cn)
    prod_sh = roc.sharpe(pn)
    boot_idx = boot_df.set_index(["series", "metric"])
    cand_lo = boot_idx.loc[("candidate", "ann_return"), "ci_lo_5pct"]
    prod_hi = boot_idx.loc[("production", "ann_return"), "ci_hi_95pct"]
    if pd.notna(cand_lo) and pd.notna(prod_hi) and cand_lo > prod_hi:
        out.append("**Bootstrap 5%-quantile annual return of candidate exceeds 95%-quantile of production.**\n\n")
    else:
        out.append("**Bootstrap 5%-quantile annual return of candidate does NOT exceed 95%-quantile of production** (overlap exists).\n\n")
    out.append(f"- point-estimate annualised return: cand {cand_ar*100:+.2f}% vs prod {prod_ar*100:+.2f}%\n")
    out.append(f"- point-estimate Sharpe: cand {cand_sh:.3f} vs prod {prod_sh:.3f}\n\n")

    rep = roc.REPORTS_DIR / "backtest_realism" / f"{candidate}_simulation_audit.md"
    rep.write_text("".join(out))
    print(f"Wrote {rep}")
    print(f"Wrote {boot_csv}")


if __name__ == "__main__":
    main()
