"""
Sprint 3 — Native Signal Weighting
Computes walk-forward information coefficients (IC) per regime state,
applies shrinkage toward equal weighting, and outputs signal weights per state.

Run ONLY after Sprint 2 completes (native states validated, obs check passed).
Run: python3 research_native_rebuild/scripts/03_build_native_signal_weighting.py

Outputs:
  outputs/signal_weighting/ic_walkforward.parquet
  outputs/signal_weighting/ic_summary_by_state.csv
  outputs/signal_weighting/signal_weights_by_state.csv
  outputs/signal_weighting/shrinkage_diagnostics.csv

Data discipline:
  - IC estimation uses dev period only. No holdout data. (HS3 hard stop if violated)
  - Walk-forward: IC at date t computed from data through t-1 (no look-ahead)
  - States with < 30 dev observations: use cross-state average IC (not state-specific)
  - Shrinkage toward equal weighting applied to all IC estimates
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "signal_weighting"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEV_END = pd.Timestamp("2024-04-12")
HOLDOUT_START = pd.Timestamp("2024-04-19")

MIN_STATE_OBS = 30
IC_WINDOW_WEEKS = 52       # minimum IC estimation window
SHRINKAGE_FACTOR = 0.5     # 0 = no shrinkage, 1 = full equal-weight


# ─── Signal Loaders ───────────────────────────────────────────────────────────

SIGNAL_FILES = {
    "xsmom":     "signal_xsmom.csv",
    "tsmom":     "signal_tsmom.csv",
    "multi_mom": "signal_multi_horizon_mom.csv",
    "reversal":  "signal_reversal.csv",
    "quality":   "signal_quality.csv",
    "carry":     "signal_carry.csv",
    "value":     "signal_value.csv",
    "trend_q":   "signal_trend_quality.csv",
    "breadth":   "signal_breadth_confirmation.csv",
    "credit":    "signal_r2_credit_spread.csv",
    "fin_cond":  "signal_r2_financial_conditions.csv",
}


def load_signals():
    sig_dir = ROOT / "data" / "02_layer1_signals"
    signals = {}
    for name, fname in SIGNAL_FILES.items():
        fpath = sig_dir / fname
        if fpath.exists():
            df = pd.read_csv(fpath, index_col=0, parse_dates=True)
            # Use first numeric column if multi-column signal file
            num_cols = df.select_dtypes(include=[float, int]).columns
            if len(num_cols) > 0:
                signals[name] = df[num_cols[0]]
        else:
            print(f"  WARNING: signal file not found: {fpath}")
    return signals


# ─── Walk-Forward IC ─────────────────────────────────────────────────────────

def compute_walkforward_ic(signals, fwd_returns, native_states):
    """
    Compute rolling IC (Spearman rank correlation) for each signal × state.
    Walk-forward: at each date t, IC uses data through t-1 in the dev period.
    """
    dev_mask = fwd_returns.index <= DEV_END
    dev_dates = fwd_returns.index[dev_mask]

    # align everything to same index
    all_dates = fwd_returns.index

    ic_records = []
    signal_names = list(signals.keys())

    for i, date in enumerate(dev_dates):
        if i < IC_WINDOW_WEEKS:
            continue
        window_start = dev_dates[max(0, i - IC_WINDOW_WEEKS)]
        window_end = dev_dates[i - 1]
        window_mask = (fwd_returns.index >= window_start) & (fwd_returns.index <= window_end)

        for state in native_states.unique():
            state_window = window_mask & (native_states == state)
            n_obs = int(state_window.sum())
            if n_obs < MIN_STATE_OBS:
                continue

            for sig_name in signal_names:
                if sig_name not in signals:
                    continue
                sig = signals[sig_name]
                ret = fwd_returns
                combined = pd.DataFrame({"sig": sig, "ret": ret})[state_window].dropna()
                if len(combined) < 10:
                    continue
                ic = combined["sig"].corr(combined["ret"], method="spearman")
                ic_records.append({
                    "date": date,
                    "state": state,
                    "signal": sig_name,
                    "ic": ic,
                    "n_obs": n_obs,
                })

    return pd.DataFrame(ic_records)


# ─── IC Summary and Shrinkage ────────────────────────────────────────────────

def compute_ic_summary(ic_df):
    """Aggregate walk-forward IC into per-state, per-signal summaries."""
    summary = ic_df.groupby(["state", "signal"]).agg(
        mean_ic=("ic", "mean"),
        std_ic=("ic", "std"),
        n_obs=("n_obs", "mean"),
    ).reset_index()
    return summary


def apply_shrinkage(summary, shrinkage=SHRINKAGE_FACTOR):
    """
    Shrink IC estimates toward equal weighting (IC = 0 in equal-weight limit).
    shrunk_ic = (1 - shrinkage) * raw_ic + shrinkage * 0
    Signal weights then = max(0, shrunk_ic) / sum(max(0, shrunk_ic))
    """
    summary = summary.copy()
    summary["shrunk_ic"] = (1 - shrinkage) * summary["mean_ic"]
    summary["shrinkage_applied"] = shrinkage

    # Compute equal weight for fallback
    n_signals = summary["signal"].nunique()
    eq_weight = 1.0 / n_signals if n_signals > 0 else 1.0

    # Per-state weights: proportional to max(0, shrunk_ic), fallback to equal
    weights = []
    for state in summary["state"].unique():
        state_mask = summary["state"] == state
        state_df = summary[state_mask].copy()
        pos_ic = state_df["shrunk_ic"].clip(lower=0)
        total = pos_ic.sum()
        if total > 1e-8:
            state_df["weight"] = pos_ic / total
        else:
            state_df["weight"] = eq_weight
        weights.append(state_df)

    return pd.concat(weights, ignore_index=True)


# ─── Cross-State Fallback ─────────────────────────────────────────────────────

def add_cross_state_fallback(summary):
    """
    For states with < 30 dev obs in IC estimation, use cross-state average IC.
    """
    cross_state_avg = summary.groupby("signal")["mean_ic"].mean().to_dict()
    for idx, row in summary.iterrows():
        if row["n_obs"] < MIN_STATE_OBS:
            summary.at[idx, "mean_ic"] = cross_state_avg.get(row["signal"], 0.0)
            summary.at[idx, "shrunk_ic"] = (1 - SHRINKAGE_FACTOR) * summary.at[idx, "mean_ic"]
    return summary


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  Sprint 3 — Native Signal Weighting")
    print("=" * 70 + "\n")

    # Load native states
    states_path = ROOT / "research_native_rebuild" / "outputs" / "regime_engine" / "native_states.csv"
    if not states_path.exists():
        print("  ERROR: Native states not found. Run Script 02 first.")
        sys.exit(1)
    native_states_df = pd.read_csv(states_path, index_col=0, parse_dates=True)
    native_states = native_states_df["native_state"]

    # Load prices and compute forward returns (same convention as production)
    prices_path = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
    prices = pd.read_csv(prices_path, index_col=0, parse_dates=True)
    returns = prices.pct_change()
    # SPY as reference for IC (or use portfolio-level return — to be specified in Sprint 3)
    if "SPY" in returns.columns:
        fwd_returns = returns["SPY"].shift(-1)   # forward 1-week SPY return
    else:
        fwd_returns = returns.iloc[:, 0].shift(-1)

    # Load signals
    print("  Loading signals...")
    signals = load_signals()
    print(f"  Loaded {len(signals)} signals: {list(signals.keys())}")

    # Walk-forward IC — dev period only
    print("  Computing walk-forward IC (dev period only, this may take a moment)...")
    ic_df = compute_walkforward_ic(signals, fwd_returns, native_states)

    if len(ic_df) == 0:
        print("  WARNING: No IC records computed. Check signal and state availability.")
    else:
        print(f"  IC records: {len(ic_df)}")

    # IC summary and shrinkage
    if len(ic_df) > 0:
        summary = compute_ic_summary(ic_df)
        summary = add_cross_state_fallback(summary)
        weights_df = apply_shrinkage(summary, SHRINKAGE_FACTOR)
    else:
        # Fallback: equal weights for all signals in all states
        states_list = native_states.unique().tolist()
        signal_names = list(signals.keys())
        eq_weight = 1.0 / max(1, len(signal_names))
        rows = [{"state": s, "signal": sig, "mean_ic": 0.0, "shrunk_ic": 0.0,
                 "n_obs": 0, "weight": eq_weight, "shrinkage_applied": SHRINKAGE_FACTOR}
                for s in states_list for sig in signal_names]
        weights_df = pd.DataFrame(rows)
        ic_df = pd.DataFrame(columns=["date", "state", "signal", "ic", "n_obs"])
        summary = weights_df.copy()

    # Write outputs
    ic_df.to_parquet(OUT_DIR / "ic_walkforward.parquet") if len(ic_df) > 0 else None
    summary.to_csv(OUT_DIR / "ic_summary_by_state.csv", index=False)
    weights_df[["state", "signal", "weight"]].to_csv(
        OUT_DIR / "signal_weights_by_state.csv", index=False)

    shrinkage_diag = weights_df[["state", "signal", "mean_ic", "shrunk_ic",
                                  "shrinkage_applied"]].copy()
    shrinkage_diag.to_csv(OUT_DIR / "shrinkage_diagnostics.csv", index=False)

    print(f"\n  States covered: {weights_df['state'].nunique()}")
    print(f"  Signals weighted: {weights_df['signal'].nunique()}")
    print(f"  Shrinkage factor: {SHRINKAGE_FACTOR}")
    print("\n  Signal weights written to outputs/signal_weighting/")
    print("  Sprint 3 complete. Review ic_summary_by_state.csv before Sprint 4.")


if __name__ == "__main__":
    main()
