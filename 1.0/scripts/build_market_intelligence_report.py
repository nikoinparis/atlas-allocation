"""Layer 4 — Market Intelligence & Diagnostics report.

Reads the latest ETF return / weight / state files and writes a market
context report explaining what changed recently and whether the change
is signal-driven, regime-driven, or allocator-driven. Diagnostic only.

Outputs:
  reports/market_intelligence/latest_market_context.md
  data/research/market_intelligence/market_context_snapshot.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


REPORT_PATH = roc.REPORTS_DIR / "market_intelligence" / "latest_market_context.md"
SNAPSHOT_PATH = roc.ROOT / "data" / "research" / "market_intelligence" / "market_context_snapshot.csv"

PROXIES = {
    "HYG (high yield credit)": "HYG",
    "LQD (investment grade credit)": "LQD",
    "UUP (USD strength)": "UUP",
    "TLT (long Treasury)": "TLT",
    "IEF (intermediate Treasury)": "IEF",
    "GLD (defensive / inflation)": "GLD",
    "SPY (broad equity)": "SPY",
    "QQQ (tech / growth)": "QQQ",
    "IWM (small cap)": "IWM",
}


def cumulative_return(s: pd.Series, weeks: int) -> float:
    s = s.dropna().tail(weeks)
    if len(s) < weeks:
        return float("nan")
    return float(np.expm1(np.log1p(s).sum()))


def latest_state(state: pd.DataFrame) -> dict:
    last = state.iloc[-1]
    out = {
        "as_of": str(state.index[-1])[:10],
        "market_state": str(last.get("market_state", "")),
    }
    if "refined_state" in state.columns:
        out["refined_state"] = str(last.get("refined_state", ""))
    if "deterioration_rank_neutral_mixed" in state.columns:
        out["deterioration_rank"] = (
            float(last.get("deterioration_rank_neutral_mixed"))
            if pd.notna(last.get("deterioration_rank_neutral_mixed")) else float("nan")
        )
    if "defensive_overlay_hint" in state.columns:
        out["defensive_overlay_hint"] = int(last.get("defensive_overlay_hint", 0))
    if "risk_state" in state.columns:
        out["risk_state"] = str(last.get("risk_state", ""))
    return out


def recent_state_transitions(state: pd.DataFrame, weeks: int = 12) -> pd.DataFrame:
    sub = state.tail(weeks)
    s = sub["market_state"].astype(str)
    changes = s.ne(s.shift())
    rows = []
    for ts in sub.index[changes]:
        rows.append({
            "date": str(ts)[:10],
            "from": str(s.shift().loc[ts] if ts in s.shift().index else ""),
            "to": str(s.loc[ts]),
        })
    return pd.DataFrame(rows)


def biggest_movers(weekly: pd.DataFrame, weeks: int) -> pd.DataFrame:
    rows = []
    for c in weekly.columns:
        ret = cumulative_return(weekly[c], weeks)
        rows.append({"etf": c, "weeks": weeks, "cumulative_return": ret})
    df = pd.DataFrame(rows).dropna().sort_values("cumulative_return", ascending=False)
    return df


def biggest_weight_changes(name: str, weeks: int = 4) -> pd.DataFrame:
    w = roc.load_portfolio_weights(name)
    if w is None or len(w) < weeks + 1:
        return pd.DataFrame()
    last = w.iloc[-1]
    prior = w.iloc[-1 - weeks]
    delta = (last - prior).sort_values()
    df = pd.DataFrame({
        "etf": delta.index,
        f"weight_{prior.name.date() if hasattr(prior.name, 'date') else 'prior'}": prior.values,
        f"weight_{last.name.date() if hasattr(last.name, 'date') else 'latest'}": last.values,
        "delta": delta.values,
    }).set_index("etf").sort_values("delta", key=abs, ascending=False)
    return df.head(10)


def candidate_vs_production_diff(candidate: str) -> pd.DataFrame:
    cw = roc.load_portfolio_weights(candidate)
    pw = roc.load_portfolio_weights(roc.PRODUCTION_PIN)
    if cw is None or pw is None:
        return pd.DataFrame()
    c_last = cw.iloc[-1]
    p_last = pw.reindex(columns=cw.columns).iloc[-1]
    diff = (c_last - p_last).sort_values(key=abs, ascending=False)
    df = pd.DataFrame({
        "etf": diff.index,
        f"{candidate}": c_last.values,
        f"{roc.PRODUCTION_PIN}": p_last.values,
        "delta": diff.values,
    }).set_index("etf")
    return df.head(10)


def driver_classification(state_changed_recently: bool, weight_change_size: float,
                          big_etf_move_4w: float) -> str:
    """Heuristic: classify the dominant driver of recent change."""
    reasons = []
    if state_changed_recently:
        reasons.append("regime-driven (state transition in the last 4 weeks)")
    if weight_change_size > 0.10:
        reasons.append("allocator-driven (>10% L1 weight change in last 4 weeks)")
    if abs(big_etf_move_4w) > 0.05:
        reasons.append("market-driven (largest ETF moved >5% over 4 weeks)")
    if not reasons:
        return "no clear single driver — typical week"
    return "; ".join(reasons)


def main():
    weekly = roc.load_weekly_returns()
    try:
        state = roc.load_market_state(refined=True)
    except FileNotFoundError:
        state = roc.load_market_state(refined=False)

    ls = latest_state(state)
    rt = recent_state_transitions(state, weeks=12)

    movers_1w = biggest_movers(weekly, 1)
    movers_4w = biggest_movers(weekly, 4)
    movers_12w = biggest_movers(weekly, 12)

    # Detect candidates
    candidates_present = []
    for name in [roc.PHASEZ_Z1, roc.PHASEBB_BB1, roc.PHASEAA_AA1]:
        if (roc.LAYER3_DIR / f"portfolio_version_weights_{name}.csv").exists():
            candidates_present.append(name)
    surrogate_candidate = candidates_present[0] if candidates_present else None

    weight_changes_prod = biggest_weight_changes(roc.PRODUCTION_PIN, weeks=4)
    weight_changes_cand = biggest_weight_changes(surrogate_candidate, weeks=4) if surrogate_candidate else pd.DataFrame()
    cand_vs_prod = candidate_vs_production_diff(surrogate_candidate) if surrogate_candidate else pd.DataFrame()

    # Exposure timeline
    pw = roc.load_portfolio_weights(roc.PRODUCTION_PIN)
    if pw is not None and "BIL" in pw.columns:
        bil_last = float(pw["BIL"].iloc[-1]); bil_prior = float(pw["BIL"].iloc[-5]) if len(pw) > 5 else float("nan")
    else:
        bil_last = bil_prior = float("nan")
    if pw is not None and "SPY" in pw.columns:
        spy_last = float(pw["SPY"].iloc[-1]); spy_prior = float(pw["SPY"].iloc[-5]) if len(pw) > 5 else float("nan")
    else:
        spy_last = spy_prior = float("nan")

    state_changed_recently = (not rt.empty) and (len(rt) > 0)
    avg_weight_change = float(weight_changes_prod["delta"].abs().sum()) if not weight_changes_prod.empty else 0.0
    big_4w_move = float(movers_4w["cumulative_return"].abs().max()) if not movers_4w.empty else 0.0
    driver = driver_classification(state_changed_recently, avg_weight_change, big_4w_move)

    # ------------- Report -------------
    out = []
    out.append("# Market Intelligence Report\n\n")
    out.append(f"**As of:** {ls['as_of']}\n\n")
    out.append("## Current market state\n\n")
    for k, v in ls.items():
        out.append(f"- **{k}**: `{v}`\n")
    out.append("\n")

    out.append("## Recent state transitions (last 12 weeks)\n\n")
    if rt.empty:
        out.append("No state transitions in the last 12 weeks.\n\n")
    else:
        out.append("```\n" + rt.to_string(index=False) + "\n```\n\n")

    out.append("## Biggest ETF movers\n\n")
    out.append("**Last 1 week — top 10 up / down**\n\n")
    out.append("```\n" + pd.concat([movers_1w.head(10), movers_1w.tail(10)]).to_string(index=False, float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")
    out.append("**Last 4 weeks — top 10 up / down**\n\n")
    out.append("```\n" + pd.concat([movers_4w.head(10), movers_4w.tail(10)]).to_string(index=False, float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")
    out.append("**Last 12 weeks — top 10 up / down**\n\n")
    out.append("```\n" + pd.concat([movers_12w.head(10), movers_12w.tail(10)]).to_string(index=False, float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")

    out.append("## Risk-proxy snapshot\n\n")
    rows = []
    for label, ticker in PROXIES.items():
        if ticker in weekly.columns:
            rows.append({
                "proxy": label,
                "ticker": ticker,
                "1w": cumulative_return(weekly[ticker], 1),
                "4w": cumulative_return(weekly[ticker], 4),
                "12w": cumulative_return(weekly[ticker], 12),
            })
        else:
            rows.append({"proxy": label, "ticker": ticker, "1w": float("nan"),
                         "4w": float("nan"), "12w": float("nan")})
    proxy_df = pd.DataFrame(rows)
    out.append("```\n" + proxy_df.to_string(index=False, float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")

    out.append("## Production portfolio: biggest ETF weight changes (last 4 weeks)\n\n")
    if weight_changes_prod.empty:
        out.append(roc.warn_section("Production portfolio weights not available."))
    else:
        out.append("```\n" + weight_changes_prod.to_string(float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")

    out.append("## SPY / BIL exposure change (production, last 4 weeks)\n\n")
    out.append(f"- BIL/cash: {roc.fmt_pct(bil_prior)} → {roc.fmt_pct(bil_last)} (Δ {roc.fmt_pct((bil_last or 0) - (bil_prior or 0))})\n")
    out.append(f"- SPY: {roc.fmt_pct(spy_prior)} → {roc.fmt_pct(spy_last)} (Δ {roc.fmt_pct((spy_last or 0) - (spy_prior or 0))})\n\n")

    if surrogate_candidate is not None:
        out.append(f"## Candidate ({surrogate_candidate}) vs production — top weight differences\n\n")
        if cand_vs_prod.empty:
            out.append(roc.warn_section("Candidate weights not available."))
        else:
            out.append("```\n" + cand_vs_prod.to_string(float_format=lambda x: f"{x*100:+.2f}%") + "\n```\n\n")
        # concentration
        cw = roc.load_portfolio_weights(surrogate_candidate)
        pw_eff = roc.load_portfolio_weights(roc.PRODUCTION_PIN)
        if cw is not None and pw_eff is not None:
            cand_max = float(cw.iloc[-1].max())
            cand_bil = float(cw.iloc[-1].get("BIL", 0.0))
            prod_max = float(pw_eff.iloc[-1].max())
            prod_bil = float(pw_eff.iloc[-1].get("BIL", 0.0))
            out.append("**Concentration / defensive split (latest week)**\n\n")
            out.append(f"- candidate max single-ETF weight: {cand_max*100:.2f}% (production: {prod_max*100:.2f}%)\n")
            out.append(f"- candidate BIL/cash exposure: {cand_bil*100:.2f}% (production: {prod_bil*100:.2f}%)\n\n")

    out.append("## Dominant driver of recent change (heuristic)\n\n")
    out.append(f"**{driver}**\n\n")
    out.append("This is a diagnostic classification, not a predictive claim. The Layer 4 report exists to make recent changes inspectable, not to forecast them.\n\n")

    out.append("## Warnings\n\n")
    warnings = []
    if pw is None: warnings.append("Production portfolio weights file not loaded.")
    if surrogate_candidate is None: warnings.append("No recent candidate (Z1 / BB1 / AA1) weights available for comparison.")
    if "refined_state" not in state.columns: warnings.append("Refined state file not present; running on original state only.")
    if not warnings:
        out.append("None.\n")
    for w in warnings:
        out.append(f"- {w}\n")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("".join(out))

    # Snapshot CSV
    snap = pd.DataFrame([{
        "as_of": ls["as_of"],
        "market_state": ls.get("market_state", ""),
        "refined_state": ls.get("refined_state", ""),
        "deterioration_rank": ls.get("deterioration_rank", float("nan")),
        "defensive_overlay_hint": ls.get("defensive_overlay_hint", float("nan")),
        "risk_state": ls.get("risk_state", ""),
        "production_BIL": bil_last,
        "production_SPY": spy_last,
        "biggest_4w_move_abs": big_4w_move,
        "driver": driver,
    }])
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    snap.to_csv(SNAPSHOT_PATH, index=False)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
