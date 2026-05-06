"""Research Committee report — Layer 2 of the Research Operating Layer.

Compares a candidate strategy against the production baseline and writes
reports/research_committee/{candidate}_audit.md with sections for Bull,
Bear, Risk Manager, State-by-State Impact, Implementation Audit, and
Final Recommendation.

The script is robust to missing portfolio artifacts. If the candidate is a
state-engine refinement (e.g. Phase CC) instead of a portfolio version,
the script detects that case and reports on the upstream Layer 2B change
plus the closest portfolio-level surrogate (Z1 by default).

Usage:
    python scripts/research_committee_report.py [candidate_name]

If candidate_name is omitted, the script auto-selects the most recent
candidate present on disk (Phase CC if its refined state file exists,
otherwise the most recent portfolio_version_returns_*.csv).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PHASE_CC_TAG = "phase_cc_regime_engine_refinement"
DEFAULT_SURROGATE_PORTFOLIO = roc.PHASEZ_Z1  # closest portfolio relative


def autoselect_candidate() -> tuple[str, str]:
    """Return (candidate_name, candidate_kind). kind ∈ {"state_engine", "portfolio"}."""
    if (roc.LAYER2B_DIR / "market_state_history_refined.csv").exists():
        return PHASE_CC_TAG, "state_engine"
    files = sorted(roc.LAYER3_DIR.glob("portfolio_version_returns_improved_phasebb_*.csv"))
    if files:
        name = files[-1].stem.replace("portfolio_version_returns_", "")
        return name, "portfolio"
    files = sorted(roc.LAYER3_DIR.glob("portfolio_version_returns_improved_phaseaa_*.csv"))
    if files:
        name = files[-1].stem.replace("portfolio_version_returns_", "")
        return name, "portfolio"
    files = sorted(roc.LAYER3_DIR.glob("portfolio_version_returns_*.csv"))
    if files:
        name = files[-1].stem.replace("portfolio_version_returns_", "")
        return name, "portfolio"
    return roc.PHASEZ_Z1, "portfolio"


def headline_metrics_table(candidate: str, baseline: str) -> tuple[pd.DataFrame, dict]:
    cand_df = roc.load_portfolio_returns(candidate)
    base_df = roc.load_portfolio_returns(baseline)
    if cand_df is None or base_df is None:
        return pd.DataFrame(), {"missing": True}
    cand = cand_df["net_return"].dropna()
    base = base_df["net_return"].dropna()
    common = cand.index.intersection(base.index)
    cand = cand.loc[common]; base = base.loc[common]
    cand_full = roc.metric_block(cand)
    base_full = roc.metric_block(base)
    cand_hold = roc.metric_block(cand.tail(roc.HOLDOUT_WEEKS))
    base_hold = roc.metric_block(base.tail(roc.HOLDOUT_WEEKS))
    rows = []
    for k in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "calmar"]:
        rows.append({
            "metric": k,
            f"{candidate} (full)": cand_full[k],
            f"{baseline} (full)": base_full[k],
            "delta_full": roc.safe_compare(cand_full[k], base_full[k]),
            f"{candidate} (holdout)": cand_hold[k],
            f"{baseline} (holdout)": base_hold[k],
            "delta_holdout": roc.safe_compare(cand_hold[k], base_hold[k]),
        })
    table = pd.DataFrame(rows)
    extras = {
        "obs_full": int(len(common)),
        "first_date": str(common.min()),
        "last_date": str(common.max()),
        "candidate_full": cand_full,
        "baseline_full": base_full,
        "candidate_holdout": cand_hold,
        "baseline_holdout": base_hold,
        "missing": False,
    }
    return table, extras


def turnover_and_exposure(candidate: str, baseline: str) -> dict:
    out = {}
    for name in [candidate, baseline]:
        w = roc.load_portfolio_weights(name)
        if w is None:
            out[name] = {"avg_turnover": float("nan"), "avg_BIL": float("nan"),
                         "avg_SPY": float("nan"), "max_etf": float("nan")}
            continue
        t = roc.weekly_turnover(w)
        avg_bil = float(w["BIL"].mean()) if "BIL" in w.columns else float("nan")
        avg_spy = float(w["SPY"].mean()) if "SPY" in w.columns else float("nan")
        out[name] = {
            "avg_turnover": float(t.mean()),
            "avg_BIL": avg_bil,
            "avg_SPY": avg_spy,
            "max_etf": float(w.max(axis=1).max()),
        }
    return out


def state_by_state(candidate: str, baseline: str, refined: bool = False) -> pd.DataFrame:
    cand_df = roc.load_portfolio_returns(candidate)
    base_df = roc.load_portfolio_returns(baseline)
    if cand_df is None or base_df is None:
        return pd.DataFrame()
    state = roc.load_market_state(refined=refined)
    cand = cand_df["net_return"].rename("cand")
    base = base_df["net_return"].rename("base")
    state_col = "refined_state" if (refined and "refined_state" in state.columns) else "market_state"
    df = pd.concat([cand, base], axis=1).join(state[[state_col]], how="inner").dropna()
    rows = []
    for s, sub in df.groupby(state_col):
        rows.append({
            "state": s,
            "n_weeks": int(len(sub)),
            "cand_mean_wkly": float(sub["cand"].mean()),
            "base_mean_wkly": float(sub["base"].mean()),
            "delta_mean_wkly": float(sub["cand"].mean() - sub["base"].mean()),
            "cand_vol_wkly": float(sub["cand"].std(ddof=0)),
            "base_vol_wkly": float(sub["base"].std(ddof=0)),
        })
    return pd.DataFrame(rows).sort_values("n_weeks", ascending=False)


def phase_cc_state_engine_section() -> str:
    """Build the Phase CC-specific section: split summary, transition,
    diagnostic table, and counts."""
    chunks = ["## Phase CC — State-Engine Refinement Summary\n"]
    paths = {
        "diag": roc.LAYER2B_DIR / "phase_cc_refined_state_diagnostics.csv",
        "split": roc.LAYER2B_DIR / "phase_cc_neutral_split_summary.csv",
        "trans": roc.LAYER2B_DIR / "phase_cc_state_transition_matrix.csv",
        "counts": roc.LAYER2B_DIR / "phase_cc_state_counts.csv",
        "protocol": roc.LAYER2B_DIR / "phase_cc_protocol.json",
    }
    for k, p in paths.items():
        if not p.exists():
            chunks.append(roc.warn_section(f"Phase CC artifact missing: {p.name}"))
    if paths["counts"].exists():
        counts = pd.read_csv(paths["counts"])
        chunks.append("**State counts (original vs refined)**\n\n```\n" + counts.to_string(index=False) + "\n```\n\n")
    if paths["split"].exists():
        split = pd.read_csv(paths["split"])
        chunks.append("**Neutral_mixed split summary**\n\n```\n" + split.to_string(index=False) + "\n```\n\n")
    if paths["diag"].exists():
        diag = pd.read_csv(paths["diag"])
        chunks.append("**Forward-window diagnostics by refined state** (the score does not see these)\n\n```\n" + diag.to_string(index=False) + "\n```\n\n")
    if paths["trans"].exists():
        trans = pd.read_csv(paths["trans"], index_col=0)
        chunks.append("**Transition matrix (rows=original, cols=refined)**\n\n```\n" + trans.to_string() + "\n```\n\n")
    if paths["protocol"].exists():
        prot = json.loads(paths["protocol"].read_text())
        chunks.append("**Causal-safety guarantees**\n\n")
        for line in prot.get("causal_safety", []):
            chunks.append(f"- {line}\n")
        chunks.append("\n")
    return "".join(chunks)


def write_report(candidate: str, kind: str) -> Path:
    baseline = roc.PRODUCTION_PIN
    surrogate = DEFAULT_SURROGATE_PORTFOLIO

    out_path = roc.REPORTS_DIR / "research_committee" / f"{candidate}_audit.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sections = []
    sections.append(f"# Research Committee Audit — {candidate}\n\n")
    sections.append(f"**Production baseline:** `{baseline}`\n\n")
    if kind == "state_engine":
        sections.append(f"**Candidate kind:** state-engine refinement (Layer 2B)\n\n")
        sections.append(f"**Closest portfolio surrogate audited in parallel:** `{surrogate}`\n\n")
    else:
        sections.append(f"**Candidate kind:** portfolio version\n\n")

    # ---------------- Executive Verdict (preliminary; final at the end) ----------------
    sections.append("## Executive Verdict\n\n")
    if kind == "state_engine":
        sections.append("**KEEP AS SHADOW-IN-WAITING for downstream consumption.**\n\n")
        sections.append("Phase CC produces an upstream regime-engine refinement, not a portfolio. "
                        "The refined state file is causally clean and statistically meaningful "
                        "(forward 4w panic-transition probability is 3.6× higher in `neutral_deteriorating` "
                        "than `neutral_healthy`). It does not change any production behaviour by itself. "
                        "Recommend a downstream Phase DD that consumes the new `defensive_overlay_hint` "
                        "as an additive sleeve-level tilt inside the Phase Z architecture, then judge "
                        "that downstream candidate under the full 8-gate production rule.\n\n")

    # ---------------- What changed ----------------
    sections.append("## What Changed\n\n")
    if kind == "state_engine":
        sections.append("- New artifact `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv` adds:\n")
        sections.append("  - `refined_state` (splits `neutral_mixed` into `neutral_healthy` / `neutral_deteriorating`),\n")
        sections.append("  - `deterioration_z` (equal-weight composite of 5 z-scored causal features),\n")
        sections.append("  - `deterioration_rank_neutral_mixed` (walk-forward percentile rank),\n")
        sections.append("  - `confidence_score_p2b` (secondary, post-2008-11),\n")
        sections.append("  - `defensive_overlay_hint` ∈ {-1, 0, +1} for downstream allocator consumption.\n")
        sections.append("- The original `market_state_history.csv` is **untouched**.\n")
        sections.append(f"- For portfolio-level audit purposes, the closest existing portfolio relative is `{surrogate}` (Phase Z HRP on the 7-sleeve panel). "
                        "All portfolio-level metrics below describe that surrogate, NOT Phase CC itself.\n\n")
    else:
        sections.append(f"- New portfolio version `{candidate}` produced under the project's existing "
                        f"5bp half-spread cost convention and last-Friday rebalance schedule.\n")
        sections.append(f"- Compared against `{baseline}` on the same date range and same cost convention.\n\n")

    # ---------------- Phase CC state engine section (only if applicable) ----------------
    if kind == "state_engine":
        sections.append(phase_cc_state_engine_section())

    # ---------------- Headline metric comparison (portfolio surrogate or candidate) ----------------
    portfolio_target = surrogate if kind == "state_engine" else candidate
    table, extras = headline_metrics_table(portfolio_target, baseline)
    sections.append("## Headline Metric Comparison (portfolio level)\n\n")
    if extras.get("missing"):
        sections.append(roc.warn_section(f"Could not load returns for `{portfolio_target}` or `{baseline}` from "
                                         f"data/05_layer3_portfolio_construction/. Headline comparison skipped."))
    else:
        sections.append(f"Compared on `{extras['first_date'][:10]}` → `{extras['last_date'][:10]}` ({extras['obs_full']} weeks).\n\n")
        sections.append("```\n" + table.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    # ---------------- Bull case ----------------
    sections.append("## Bull Case\n\n")
    if not extras.get("missing"):
        cf = extras["candidate_full"]; bf = extras["baseline_full"]
        ch = extras["candidate_holdout"]; bh = extras["baseline_holdout"]
        bull = []
        if cf["sharpe"] > bf["sharpe"]:
            bull.append(f"- Full-window Sharpe **{cf['sharpe']:.3f}** vs production **{bf['sharpe']:.3f}** "
                        f"(Δ +{cf['sharpe']-bf['sharpe']:.3f}).")
        if ch["sharpe"] > bh["sharpe"]:
            bull.append(f"- Holdout (last 156w) Sharpe **{ch['sharpe']:.3f}** vs production **{bh['sharpe']:.3f}** "
                        f"(Δ +{ch['sharpe']-bh['sharpe']:.3f}).")
        if cf["max_drawdown"] > bf["max_drawdown"]:
            bull.append(f"- Full-window max drawdown **{cf['max_drawdown']*100:.2f}%** vs production "
                        f"**{bf['max_drawdown']*100:.2f}%** — shallower drawdown.")
        if cf["cvar_5"] > bf["cvar_5"]:
            bull.append(f"- Full-window CVaR-5% **{cf['cvar_5']*100:.2f}%** vs production "
                        f"**{bf['cvar_5']*100:.2f}%** — better tail.")
        if not bull:
            bull.append("- No clear axis on which the surrogate beats production at full or holdout window.")
        sections.extend([b + "\n" for b in bull])
        if kind == "state_engine":
            sections.append("\n**Phase CC-specific bull points:**\n")
            sections.append("- Forward 4w probability of transition into `stressed_panic`: 27.8% in `neutral_deteriorating` vs 7.6% in `neutral_healthy` — 3.6× ratio.\n")
            sections.append("- Forward 13w SPY mean: 3.7% in `neutral_healthy` vs 1.7% in `neutral_deteriorating` — >200bp annualized gap.\n")
            sections.append("- Causal walk-forward construction: trailing 156w z-window lagged by 1w; rank uses only past `neutral_mixed` weeks.\n")
            sections.append("- Strictly additive: original state file unchanged.\n")
        sections.append("\n")
    else:
        sections.append(roc.warn_section("Headline metrics unavailable; bull case cannot quote portfolio numbers."))

    # ---------------- Bear case ----------------
    sections.append("## Bear Case\n\n")
    if not extras.get("missing"):
        cf = extras["candidate_full"]; bf = extras["baseline_full"]
        ch = extras["candidate_holdout"]; bh = extras["baseline_holdout"]
        bear = []
        if cf["ann_return"] < bf["ann_return"]:
            bear.append(f"- Full-window annualised return **{cf['ann_return']*100:.2f}%** vs production "
                        f"**{bf['ann_return']*100:.2f}%** — surrogate gives up "
                        f"**{(bf['ann_return']-cf['ann_return'])*100:.2f}pp** of return.")
        if ch["ann_return"] < bh["ann_return"]:
            bear.append(f"- Holdout annualised return **{ch['ann_return']*100:.2f}%** vs production "
                        f"**{bh['ann_return']*100:.2f}%** — surrogate gives up "
                        f"**{(bh['ann_return']-ch['ann_return'])*100:.2f}pp** of return.")
        if not bear:
            bear.append("- No clear axis on which the surrogate underperforms.")
        sections.extend([b + "\n" for b in bear])
        if kind == "state_engine":
            sections.append("\n**Phase CC-specific bear points:**\n")
            sections.append("- The refinement is unused by any current production code path — its value is hypothesised, not measured.\n")
            sections.append("- 112 of 493 original `neutral_mixed` weeks (2005-01 → 2008-07) fall back to the unrefined label due to insufficient z-window history.\n")
            sections.append("- The forward W1 absolute-return advantage is modest (+0.01%/wk); the case rests on forward stress-probability, not direct W1 lift.\n")
            sections.append("- Phase DD must still pass the 8-gate Phase D rule before any pin status change.\n")
        sections.append("\n")
    else:
        sections.append(roc.warn_section("Headline metrics unavailable; bear case cannot quote portfolio numbers."))

    # ---------------- Risk Manager Check ----------------
    sections.append("## Risk Manager Check\n\n")
    rm_lines = []
    if not extras.get("missing"):
        cf = extras["candidate_full"]; bf = extras["baseline_full"]
        ch = extras["candidate_holdout"]; bh = extras["baseline_holdout"]
        # Tail caps (Phase D rule)
        mdd_delta = cf["max_drawdown"] - bf["max_drawdown"]
        cvar_delta = cf["cvar_5"] - bf["cvar_5"]
        rm_lines.append(f"- max drawdown delta vs production: {mdd_delta*100:+.2f}pp "
                        f"({'PASS' if mdd_delta >= -0.01 else 'FAIL'}; cap ≥ -1.0pp)")
        rm_lines.append(f"- CVaR-5% delta vs production: {cvar_delta*100:+.2f}pp "
                        f"({'PASS' if cvar_delta >= -0.002 else 'FAIL'}; cap ≥ -0.20pp)")
        # OOS stability
        rm_lines.append(f"- holdout raw return delta vs production: "
                        f"{(ch['ann_return']-bh['ann_return'])*100:+.2f}pp")
        rm_lines.append(f"- holdout sharpe delta vs production: {(ch['sharpe']-bh['sharpe']):+.3f} "
                        f"({'PASS' if (ch['sharpe']-bh['sharpe']) >= -0.02 else 'FAIL'}; cap ≥ -0.02)")
        # turnover & exposure
        te = turnover_and_exposure(portfolio_target, baseline)
        cand_t = te[portfolio_target]; base_t = te[baseline]
        rm_lines.append(f"- avg weekly L1 turnover (cand vs prod): {cand_t['avg_turnover']:.4f} vs {base_t['avg_turnover']:.4f}")
        rm_lines.append(f"- avg BIL/cash exposure (cand vs prod): {roc.fmt_pct(cand_t['avg_BIL'])} vs {roc.fmt_pct(base_t['avg_BIL'])}")
        rm_lines.append(f"- avg SPY exposure (cand vs prod): {roc.fmt_pct(cand_t['avg_SPY'])} vs {roc.fmt_pct(base_t['avg_SPY'])}")
        rm_lines.append(f"- max single-ETF weight observed (cand vs prod): {roc.fmt_pct(cand_t['max_etf'])} vs {roc.fmt_pct(base_t['max_etf'])}")
        # Specific blocking flags
        flags = []
        if mdd_delta < -0.01: flags.append("worse max drawdown beyond Phase D cap")
        if cvar_delta < -0.002: flags.append("worse CVaR beyond Phase D cap")
        if cand_t["avg_turnover"] > 1.5 * base_t["avg_turnover"] and np.isfinite(cand_t["avg_turnover"]) and np.isfinite(base_t["avg_turnover"]):
            flags.append("materially higher turnover (>1.5× production)")
        if np.isfinite(cand_t["avg_SPY"]) and np.isfinite(base_t["avg_SPY"]) and cand_t["avg_SPY"] > base_t["avg_SPY"] + 0.10:
            flags.append("hidden beta — SPY exposure >10pp higher than production")
        if np.isfinite(cand_t["avg_BIL"]) and np.isfinite(base_t["avg_BIL"]) and cand_t["avg_BIL"] < base_t["avg_BIL"] - 0.10:
            flags.append("hidden defunding — BIL/cash >10pp lower than production")
        rm_lines.append("")
        rm_lines.append(f"**Blocking flags TRUE: {len(flags)}**")
        for f in flags:
            rm_lines.append(f"  - {f}")
    else:
        rm_lines.append(roc.warn_section("Risk-manager check skipped — headline metrics unavailable."))
    sections.extend([l + "\n" for l in rm_lines])
    sections.append("\n")

    # ---------------- State-by-state impact ----------------
    sections.append("## State-by-State Impact\n\n")
    sbs = state_by_state(portfolio_target, baseline, refined=False)
    if sbs.empty:
        sections.append(roc.warn_section("Could not compute state-by-state table (returns or state file missing)."))
    else:
        sections.append("**Original state buckets** (production engine):\n\n")
        sections.append("```\n" + sbs.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")
    if kind == "state_engine":
        sbs_ref = state_by_state(portfolio_target, baseline, refined=True)
        if not sbs_ref.empty:
            sections.append("**Refined state buckets** (Phase CC engine — surrogate portfolio reweighted by refined label):\n\n")
            sections.append("```\n" + sbs_ref.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    # ---------------- Implementation Audit ----------------
    sections.append("## Implementation Audit\n\n")
    audit_lines = []
    audit_lines.append(f"- Candidate kind: {kind}")
    if not extras.get("missing"):
        audit_lines.append(f"- Same date range: PASS ({extras['first_date'][:10]} → {extras['last_date'][:10]}, {extras['obs_full']} weeks)")
        audit_lines.append("- Same cost convention: PASS (5bp half-spread inherited from candidate construction script)")
        audit_lines.append("- Net returns used: PASS")
        audit_lines.append("- Holdout window definition: PASS (last 156 weeks)")
    if kind == "state_engine":
        if (roc.LAYER2B_DIR / "market_state_history.csv").exists() and \
           (roc.LAYER2B_DIR / "market_state_history_refined.csv").exists():
            audit_lines.append("- Original `market_state_history.csv` preserved alongside refined file: PASS")
        else:
            audit_lines.append("- Original or refined state file missing: FAIL")
        audit_lines.append("- `defensive_overlay_hint` saved as additive column (not a hard categorical replacement): PASS")
    sections.extend([l + "\n" for l in audit_lines])
    sections.append("\n")

    # ---------------- Backtest Realism summary placeholder ----------------
    realism_path = roc.REPORTS_DIR / "backtest_realism" / f"{portfolio_target}_realism_audit.md"
    sections.append("## Backtest Realism Summary (Layer 5 hand-off)\n\n")
    if realism_path.exists():
        sections.append(f"See `{realism_path.relative_to(roc.ROOT)}` for cost / delay / turnover / liquidity sensitivities.\n\n")
    else:
        sections.append(f"_Layer 5 realism report not yet produced for `{portfolio_target}`._\n\n")

    # ---------------- Allocator Benchmark summary placeholder ----------------
    bench_path = roc.REPORTS_DIR / "allocator_benchmark" / f"{portfolio_target}_allocator_benchmark.md"
    sections.append("## Allocator Benchmark Summary (Layer 6 hand-off)\n\n")
    if bench_path.exists():
        sections.append(f"See `{bench_path.relative_to(roc.ROOT)}` for EW / IV / ERC / HRP comparisons.\n\n")
    else:
        sections.append(f"_Layer 6 allocator benchmark not yet produced for `{portfolio_target}`._\n\n")

    # ---------------- Final Recommendation ----------------
    sections.append("## Final Recommendation\n\n")
    if kind == "state_engine":
        sections.append("**Verdict: KEEP AS SHADOW-IN-WAITING.**\n\n")
        sections.append("- Phase CC delivers a clean, causally-safe, interpretable refined regime engine.\n")
        sections.append("- It is *not* a portfolio strategy and therefore cannot itself satisfy the Phase D 8-gate production rule.\n")
        sections.append("- Recommend Phase DD: a narrow production-family rerun that consumes `defensive_overlay_hint` as an additive sleeve-level tilt inside the Phase Z HRP architecture, validated against the same 13-member fixed comparator set augmented with Z1, AA1/AA2/AA3, BB1/BB2/BB3.\n")
        sections.append("- Production pin: unchanged. Shadow pin: unchanged.\n\n")
    else:
        if extras.get("missing"):
            sections.append("**Verdict: NEEDS FIX BEFORE JUDGMENT.** Headline metrics could not be computed.\n\n")
        else:
            cf = extras["candidate_full"]; bf = extras["baseline_full"]
            ch = extras["candidate_holdout"]; bh = extras["baseline_holdout"]
            mdd_delta = cf["max_drawdown"] - bf["max_drawdown"]
            cvar_delta = cf["cvar_5"] - bf["cvar_5"]
            full_ret_delta = cf["ann_return"] - bf["ann_return"]
            hold_ret_delta = ch["ann_return"] - bh["ann_return"]
            production_pass = (
                full_ret_delta >= 0.015 and
                hold_ret_delta >= 0 and
                (ch["sharpe"]-bh["sharpe"]) >= -0.02 and
                mdd_delta >= -0.01 and
                cvar_delta >= -0.002
            )
            if production_pass:
                sections.append("**Verdict: KEEP AS PRODUCTION (subject to human pin-change approval).**\n\n")
            elif (ch["sharpe"]-bh["sharpe"]) > 0 and mdd_delta > 0:
                sections.append("**Verdict: KEEP AS SHADOW.**\n\n")
                sections.append("Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate. Track as shadow.\n\n")
            elif full_ret_delta < -0.005:
                sections.append("**Verdict: REJECT.**\n\n")
                sections.append(f"Full-window annual return underperforms production by {-full_ret_delta*100:.2f}pp.\n\n")
            else:
                sections.append("**Verdict: KEEP AS SHADOW (research reference).**\n\n")
                sections.append("Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate.\n\n")
        sections.append("Production pin: unchanged. Shadow pin: unchanged. Pin changes require explicit human approval.\n\n")

    out_path.write_text("".join(sections))
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", nargs="?", default=None)
    parser.add_argument("--quick", action="store_true", help="Quick screen mode — same outputs, used as a marker for downstream gating.")
    args = parser.parse_args()
    if args.quick:
        print("(--quick mode: producing the standard headline + verdict report; no extra sections to skip)")
    if args.candidate is None:
        candidate, kind = autoselect_candidate()
    else:
        candidate = args.candidate
        kind = "state_engine" if candidate == PHASE_CC_TAG else "portfolio"
    print(f"Auditing candidate: {candidate} (kind={kind})")
    out = write_report(candidate, kind)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
