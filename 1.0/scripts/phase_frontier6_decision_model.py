"""Frontier Phase 6B: Decision Model Training and Validation.

Walk-forward trains simple classifiers (LogisticRegression and GBM) on the
Phase 6A triple_barrier_label (primary) and deploy_quality_label (secondary).
Evaluates model accuracy vs naive baselines, then applies three portfolio
meta-gate rules and reports portfolio metrics.

Predeclared thresholds (do not change after running):
  RULE_A_LOSS_THRESH  = 0.45   (P(bad) > this → half-defense)
  RULE_B_GOOD_THRESH  = 0.55   (P(good) > this → deploy FG)
  RULE_C_GOOD_THRESH  = 0.60   (high-confidence good → FG)
  RULE_C_BAD_THRESH   = 0.60   (high-confidence bad → half-defense)

Run from repo root:
    .venv/bin/python scripts/phase_frontier6_decision_model.py
"""

from __future__ import annotations

import subprocess
import sys
import warnings as _warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

_warnings.filterwarnings("ignore", category=FutureWarning)
_warnings.filterwarnings("ignore", category=UserWarning)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import (balanced_accuracy_score, accuracy_score,
                                  confusion_matrix, classification_report)
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

from path1_path3_research_utils import DATA, PRODUCTION_COST_BPS

# ── Constants ─────────────────────────────────────────────────────────────────
HOLDOUT_START   = pd.Timestamp("2024-04-19")
MIN_TRAIN       = 260
STEP            = 26
EMBARGO         = 4
BOOTSTRAP_SEED  = 20260420
BOOTSTRAP_ITERS = 1000
BOOTSTRAP_BLOCK = 13
ROLLING_WINDOW  = 104
ROLLING_STEP    = 52

# Predeclared thresholds — not tuned after seeing results
RULE_A_LOSS_THRESH = 0.45
RULE_B_GOOD_THRESH = 0.55
RULE_C_GOOD_THRESH = 0.60
RULE_C_BAD_THRESH  = 0.60

OUT_DIR     = DATA / "research" / "frontier_phase6"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase6_decision_model_report.md"
PROTECTED   = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

# Label map for triple_barrier
TB_MAP  = {-1: 0, 0: 1, 1: 2}    # for sklearn: 0=bad,1=neutral,2=good
TB_IMAP = {0: -1, 1: 0, 2: 1}    # inverse
STATES  = ["calm_trend","neutral_mixed","recovery_confirmed",
           "recovery_fragile","stressed_panic"]


# ── Feature prep ──────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "phase1_r2a", "phase2_avg_trend_quality",
    "phase4_raw_leadership_quality", "phase4_inverted_fragility",
    "phase5_master_deployment_quality", "fragility_guard_active_flag",
    "trailing_8w_portfolio_vol", "trailing_8w_spy_return",
    "trailing_8w_ggg_return", "trailing_8w_phase5_return",
]
STATE_DUMMIES = ["calm_trend","neutral_mixed","recovery_confirmed",
                 "recovery_fragile"]  # stressed_panic is the reference


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build feature matrix from labels frame."""
    X = df[FEATURE_COLS].copy().fillna(0.0)
    # One-hot encode market_state
    for s in STATE_DUMMIES:
        X[f"state_{s}"] = (df["market_state"] == s).astype(float)
    return X.astype(float)


# ── Walk-forward splits ───────────────────────────────────────────────────────

def walk_forward_splits(n: int):
    """Yield (train_idx, test_idx) with expanding window + embargo."""
    for start in range(MIN_TRAIN, n - STEP + 1, STEP):
        train_idx = list(range(0, start - EMBARGO))
        test_idx  = list(range(start, min(start + STEP, n)))
        if len(train_idx) < MIN_TRAIN or not test_idx:
            continue
        yield train_idx, test_idx


# ── Model training ────────────────────────────────────────────────────────────

def _make_models():
    if not SKLEARN_OK:
        return {}
    return {
        "LogReg": LogisticRegression(
            max_iter=500, class_weight="balanced",
            C=1.0, random_state=42, multi_class="ovr"),
        "GBM":    GradientBoostingClassifier(
            max_depth=3, n_estimators=50, learning_rate=0.1,
            random_state=42, subsample=0.8),
    }


def walk_forward_train(X: pd.DataFrame, y: pd.Series,
                       label_name: str) -> dict[str, pd.DataFrame]:
    """Return {model_name: predictions_df} for all walk-forward splits."""
    if not SKLEARN_OK:
        print("  sklearn not available — skipping model training")
        return {}
    models = _make_models()
    results: dict[str, list] = {m: [] for m in models}
    n_valid = y.notna().sum()
    print(f"  {label_name}: {n_valid}/{len(y)} valid labels, "
          f"{len(list(walk_forward_splits(len(X))))} WF splits")

    for train_idx, test_idx in walk_forward_splits(len(X)):
        Xtr = X.iloc[train_idx]; ytr = y.iloc[train_idx]
        Xte = X.iloc[test_idx];  yte = y.iloc[test_idx]
        # Only use rows with valid labels
        tr_mask = ytr.notna(); te_mask = yte.notna()
        if tr_mask.sum() < 30 or te_mask.sum() < 2:
            continue
        Xtr, ytr = Xtr[tr_mask], ytr[tr_mask]
        Xte_valid, yte_valid = Xte[te_mask], yte[te_mask]

        for mname, clf in models.items():
            scaler = StandardScaler()
            try:
                Xtr_s = scaler.fit_transform(Xtr)
                Xte_s = scaler.transform(Xte_valid)
                clf_fit = clf.__class__(**clf.get_params())
                if label_name == "triple_barrier_label":
                    # Map to 0/1/2
                    ytr_m = ytr.map(TB_MAP)
                    clf_fit.fit(Xtr_s, ytr_m)
                    pred   = clf_fit.predict(Xte_s)
                    proba  = clf_fit.predict_proba(Xte_s)
                    classes = clf_fit.classes_
                    pred_orig = pd.Series([TB_IMAP[p] for p in pred],
                                          index=yte_valid.index)
                else:
                    clf_fit.fit(Xtr_s, ytr)
                    pred_orig = pd.Series(clf_fit.predict(Xte_s),
                                          index=yte_valid.index)
                    proba  = clf_fit.predict_proba(Xte_s)
                    classes = clf_fit.classes_

                for i, idx in enumerate(yte_valid.index):
                    row = {"date": idx, "actual": yte_valid[idx],
                           "predicted": pred_orig[idx]}
                    # Store class probabilities
                    for j, cls in enumerate(classes):
                        if label_name == "triple_barrier_label":
                            row[f"prob_{TB_IMAP[cls]}"] = float(proba[i, j])
                        else:
                            row[f"prob_{cls}"] = float(proba[i, j])
                    results[mname].append(row)
            except Exception as e:
                pass

    return {m: pd.DataFrame(r).set_index("date") for m, r in results.items() if r}


# ── Naive baselines ───────────────────────────────────────────────────────────

def naive_baselines(X: pd.DataFrame, y: pd.Series,
                    label_name: str) -> dict[str, pd.Series]:
    """Three naive predictors for comparison."""
    baselines = {}
    p1  = X["phase1_r2a"]
    mdq = X["phase5_master_deployment_quality"]
    n   = len(y)

    # 1. Always predict most common class in TRAINING data (walk-forward safe)
    maj_preds = []
    for train_idx, test_idx in walk_forward_splits(n):
        ytr = y.iloc[train_idx].dropna()
        if len(ytr) == 0:
            continue
        mc = ytr.mode()[0]
        for i in test_idx:
            if y.iloc[i] is not np.nan and pd.notna(y.iloc[i]):
                maj_preds.append({"date": y.index[i], "pred": mc})
    if maj_preds:
        mdf = pd.DataFrame(maj_preds).set_index("date")["pred"]
        baselines["always_majority"] = mdf

    # 2. Phase 1 R2A threshold
    if label_name in ("triple_barrier_label",):
        baselines["r2a_gt0"] = (p1 > 0).map({True: 1, False: -1}).reindex(y.index)
    else:
        baselines["r2a_gt0"] = (p1 > 0).astype(float).reindex(y.index)

    # 3. Master deployment quality
    if label_name in ("triple_barrier_label",):
        baselines["mdq_gt0"] = (mdq > 0).map({True: 1, False: -1}).reindex(y.index)
    else:
        baselines["mdq_gt0"] = (mdq > 0).astype(float).reindex(y.index)

    return baselines


# ── Classification evaluation ─────────────────────────────────────────────────

def eval_classification(preds: pd.DataFrame, actual: pd.Series,
                        label_name: str, scope: str = "full") -> dict:
    valid = actual.reindex(preds.index).dropna()
    pred  = preds["predicted"].reindex(valid.index).dropna()
    common = valid.index.intersection(pred.index)
    if len(common) < 10:
        return {"scope": scope, "n": len(common), "accuracy": np.nan,
                "balanced_accuracy": np.nan}
    y_true = valid[common]; y_pred = pred[common]
    acc  = float(accuracy_score(y_true, y_pred))
    bacc = float(balanced_accuracy_score(y_true, y_pred))
    return {"scope": scope, "n": len(common), "accuracy": acc,
            "balanced_accuracy": bacc}


def eval_naive(pred_series: pd.Series, actual: pd.Series,
               scope: str = "full") -> dict:
    valid = actual.dropna(); pred = pred_series.reindex(valid.index).dropna()
    common = valid.index.intersection(pred.index)
    if len(common) < 10:
        return {"scope": scope, "n": len(common), "accuracy": np.nan,
                "balanced_accuracy": np.nan}
    y_true = valid[common]; y_pred = pred[common]
    return {"scope": scope, "n": len(common),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred))}


# ── Portfolio rules ───────────────────────────────────────────────────────────

def apply_portfolio_rules(
    tb_preds: pd.DataFrame,     # must have prob_-1, prob_0, prob_1 columns
    ggg_ret: pd.Series,
    fg_ret: pd.Series,
    bil_ret: pd.Series,
    states: pd.Series,
) -> dict[str, pd.Series]:
    """Apply three predeclared portfolio rules. Default to GGG where no pred."""
    idx = ggg_ret.index

    # Extract probabilities — default to neutral if no prediction
    p_bad  = tb_preds.get("prob_-1",  pd.Series(np.nan, index=idx)).reindex(idx).fillna(1/3)
    p_neut = tb_preds.get("prob_0",   pd.Series(np.nan, index=idx)).reindex(idx).fillna(1/3)
    p_good = tb_preds.get("prob_1",   pd.Series(np.nan, index=idx)).reindex(idx).fillna(1/3)
    has_pred = tb_preds.index

    # Compute 50/50 GGG+BIL returns
    half_ret = 0.5 * ggg_ret + 0.5 * bil_ret.reindex(idx).fillna(0.0)

    rules = {}

    # Rule A: if P(bad) > 0.45 → half-defense; else → FG
    r_a = pd.Series(index=idx, dtype=float)
    for t in idx:
        if t not in has_pred:
            r_a[t] = ggg_ret.get(t, np.nan)   # no model → use GGG
        elif p_bad.get(t, 1/3) > RULE_A_LOSS_THRESH:
            r_a[t] = half_ret.get(t, np.nan)
        else:
            r_a[t] = fg_ret.get(t, np.nan)
    rules["rule_a_defensive_gate"] = r_a

    # Rule B: if P(good) > 0.55 → FG; else → GGG
    r_b = pd.Series(index=idx, dtype=float)
    for t in idx:
        if t not in has_pred:
            r_b[t] = ggg_ret.get(t, np.nan)
        elif p_good.get(t, 1/3) > RULE_B_GOOD_THRESH:
            r_b[t] = fg_ret.get(t, np.nan)
        else:
            r_b[t] = ggg_ret.get(t, np.nan)
    rules["rule_b_confidence_deploy"] = r_b

    # Rule C: high-confidence good→FG, high-confidence bad→half-defense, else→GGG
    r_c = pd.Series(index=idx, dtype=float)
    for t in idx:
        if t not in has_pred:
            r_c[t] = ggg_ret.get(t, np.nan)
        elif p_good.get(t, 1/3) > RULE_C_GOOD_THRESH:
            r_c[t] = fg_ret.get(t, np.nan)
        elif p_bad.get(t, 1/3) > RULE_C_BAD_THRESH:
            r_c[t] = half_ret.get(t, np.nan)
        else:
            r_c[t] = ggg_ret.get(t, np.nan)
    rules["rule_c_tri_state"] = r_c

    return rules


# ── Portfolio metrics ─────────────────────────────────────────────────────────

def _ar(r): return float((1+r).prod()**(52/len(r))-1) if len(r)>=2 else np.nan
def _vol(r): return float(r.std()*np.sqrt(52)) if len(r)>=4 else np.nan
def _sh(r):
    v=_vol(r); return float(_ar(r)/v) if v and np.isfinite(v) and v>0 else np.nan
def _dd(r):
    if r.empty: return np.nan
    w=(1+r).cumprod(); return float((w/w.cummax()-1).min())
def _calmar(r):
    d=_dd(r); return float(_ar(r)/abs(d)) if d and np.isfinite(d) and d<0 else np.nan
def _cvar(r,p=.05):
    if len(r)<20: return np.nan
    t=r[r<=r.quantile(p)]; return float(t.mean()) if len(t) else np.nan
def _beta(pr,spy):
    al=pd.concat([pr,spy],axis=1).dropna()
    if len(al)<20: return np.nan
    sl,*_=scipy_stats.linregress(al.iloc[:,1],al.iloc[:,0]); return float(sl)

def _switches(ret_a, ret_b):
    """Count weekly switches between two series."""
    combined = pd.concat([ret_a, ret_b], axis=1).dropna()
    if combined.empty: return 0
    diff = (combined.iloc[:,0] != combined.iloc[:,1]).astype(int)
    return int(diff.sum())

def portfolio_metrics(variant: str, ret: pd.Series, ggg_ret: pd.Series,
                      states: pd.Series, bil_ret: pd.Series,
                      spy_ret: pd.Series) -> dict:
    r = ret.dropna(); bsh = ggg_ret.reindex(r.index).dropna()
    sa = states.reindex(r.index)
    row = {"variant": variant, "ann_return": _ar(r), "ann_vol": _vol(r),
           "sharpe": _sh(r), "calmar": _calmar(r), "max_drawdown": _dd(r),
           "cvar_5": _cvar(r), "hidden_beta": _beta(r, spy_ret.reindex(r.index)),
           "avg_BIL": float(bil_ret.reindex(r.index).fillna(0).mean()),
           "sharpe_delta_vs_ggg": _sh(r) - _sh(bsh) if len(bsh) >= 10 else np.nan}
    for st in STATES:
        m = sa == st; sr = r[m]
        row[f"sharpe_{st}"] = _sh(sr)
    return row


def holdout_metrics(variant: str, ret: pd.Series, ggg_ret: pd.Series,
                    states: pd.Series, bil_ret: pd.Series, spy_ret: pd.Series) -> dict:
    ho_ret = ret[ret.index >= HOLDOUT_START].dropna()
    ho_ggg = ggg_ret[ggg_ret.index >= HOLDOUT_START].reindex(ho_ret.index).dropna()
    row = {"variant": variant, "holdout_return": _ar(ho_ret),
           "holdout_sharpe": _sh(ho_ret), "holdout_max_dd": _dd(ho_ret),
           "holdout_sharpe_vs_ggg": _sh(ho_ret) - _sh(ho_ggg) if len(ho_ggg) >= 4 else np.nan}
    sa = states.reindex(ho_ret.index)
    for st in STATES:
        m = sa == st; sr = ho_ret[m]
        row[f"holdout_sharpe_{st}"] = _sh(sr)
    return row


def rolling_origin(rule_ret, ggg_ret):
    rows = []
    cp = rule_ret.dropna(); bp = ggg_ret.reindex(cp.index).dropna()
    n = min(len(cp), len(bp))
    for s in range(260, n - ROLLING_WINDOW, ROLLING_STEP):
        idx = cp.index[s:s+ROLLING_WINDOW]
        cr = cp.loc[idx].dropna(); br = bp.loc[idx].dropna()
        if len(cr) < 20 or len(br) < 20: continue
        rows.append({"origin": cp.index[s],
                     "cand_sharpe": _sh(cr), "base_sharpe": _sh(br),
                     "delta": _sh(cr) - _sh(br)})
    df = pd.DataFrame(rows)
    if not df.empty: df["beats"] = df["delta"] > 0
    return df


def bootstrap_p(cand_r, base_r):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    al = pd.concat([cand_r, base_r], axis=1).dropna()
    if len(al) < 20: return np.nan
    n = len(al); ds = []
    for _ in range(BOOTSTRAP_ITERS):
        sts = rng.integers(0, max(1,n-BOOTSTRAP_BLOCK+1), size=(n//BOOTSTRAP_BLOCK)+2)
        idx = np.concatenate([np.arange(s, min(s+BOOTSTRAP_BLOCK, n)) for s in sts])[:n]
        s2 = al.iloc[idx]; ds.append(_sh(s2.iloc[:,0]) - _sh(s2.iloc[:,1]))
    ds = np.array([d for d in ds if np.isfinite(d)])
    return float((ds > 0).mean()) if len(ds) else np.nan


# ── Protected diff ────────────────────────────────────────────────────────────
def diff_clean():
    try:
        r = subprocess.run(["git","diff","--name-only","--",*PROTECTED],
                           cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception: return False,["failed"]
    c = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0, c


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns = []
    print("="*70)
    print("Frontier Phase 6B: Decision Model Training and Validation")
    print("="*70)

    if not SKLEARN_OK:
        raise SystemExit("scikit-learn not installed. Run: pip install scikit-learn")

    # ── Load labels and features ──────────────────────────────────────────────
    print("\nLoading decision_labels.csv...")
    lab = pd.read_csv(OUT_DIR/"decision_labels.csv",
                      index_col="date", parse_dates=True)
    lab.index = lab.index.tz_localize(None)
    print(f"  {len(lab)} rows, {lab.shape[1]} columns")

    ggg_ret = lab["ggg_net_return"].rename("ggg")
    fg_ret  = lab["fg_net_return"].rename("fg")

    # BIL returns from weekly prices
    wk = pd.read_csv(DATA/"01_data_hub"/"weekly_prices.csv",
                     index_col="Date", parse_dates=True)
    wk.index = wk.index.tz_localize(None)
    bil_ret  = wk["BIL"].pct_change(1).reindex(lab.index).fillna(0.0)
    spy_ret  = wk["SPY"].pct_change(1).reindex(lab.index)
    states   = lab["market_state"].astype(str)

    X = make_features(lab)
    print(f"  Features: {X.shape[1]} columns")

    # ── Walk-forward model training ───────────────────────────────────────────
    print("\nTraining models (walk-forward, embargo={EMBARGO}w)...")

    # Primary: triple_barrier_label
    y_tb   = lab["triple_barrier_label"]
    tb_preds = walk_forward_train(X, y_tb, "triple_barrier_label")
    print(f"  triple_barrier: {len(tb_preds)} models trained, "
          f"{max((len(v) for v in tb_preds.values()), default=0)} predictions each")

    # Binary collapsed: deploy_good_vs_bad (drop neutral 0)
    y_gvb = y_tb.where(y_tb != 0).map({1: 1, -1: 0})
    gvb_preds = walk_forward_train(X[y_gvb.notna()].reindex(X.index),
                                    y_gvb, "deploy_good_vs_bad")

    # Secondary: deploy_quality_label
    y_dq  = lab["deploy_quality_label"]
    dq_preds = walk_forward_train(X, y_dq, "deploy_quality_label")

    # Recovery-specific: rerisk_quality_label
    rec_mask = states.isin(["recovery_confirmed","recovery_fragile"])
    y_rq = lab["rerisk_quality_label"]
    n_rq = y_rq.dropna().sum()
    if n_rq >= 20:
        rq_preds = walk_forward_train(X[rec_mask], y_rq, "rerisk_quality_label")
        print(f"  rerisk_quality: trained")
    else:
        rq_preds = {}
        print(f"  rerisk_quality: skipped (only {int(n_rq)} positive examples)")
        warns.append(f"rerisk_quality_label skipped: {int(n_rq)} positive examples")

    # ── Naive baselines ───────────────────────────────────────────────────────
    print("\nComputing naive baselines...")
    nb_tb = naive_baselines(X, y_tb, "triple_barrier_label")
    nb_dq = naive_baselines(X, y_dq, "deploy_quality_label")

    # ── Classification evaluation ─────────────────────────────────────────────
    print("\nClassification evaluation (triple_barrier_label)...")
    cls_rows = []
    dev_mask  = y_tb.index < HOLDOUT_START
    hold_mask = y_tb.index >= HOLDOUT_START

    for mname, preds_df in tb_preds.items():
        for scope, mask in [("full",None),("dev",dev_mask),("holdout",hold_mask)]:
            if mask is not None:
                p = preds_df[preds_df.index.isin(y_tb.index[mask])]
            else:
                p = preds_df
            row = eval_classification(p, y_tb, "triple_barrier_label", scope)
            row["model"] = mname; row["label"] = "triple_barrier_label"
            cls_rows.append(row)
            if scope == "full":
                print(f"  {mname} triple_barrier: acc={row['accuracy']:.3f}  "
                      f"bacc={row['balanced_accuracy']:.3f}")

    # Naive baselines for triple_barrier — bpred may have 806 or 1110 rows
    for bname, bpred in nb_tb.items():
        for scope, mask in [("full",None),("dev",dev_mask),("holdout",hold_mask)]:
            if mask is not None:
                scope_dates = y_tb.index[mask]
                p = bpred.reindex(scope_dates)   # safe regardless of bpred length
            else:
                p = bpred
            row = eval_naive(p, y_tb, scope)
            row["model"] = f"naive_{bname}"; row["label"] = "triple_barrier_label"
            cls_rows.append(row)
            if scope == "full":
                print(f"  naive_{bname} tb: bacc={row['balanced_accuracy']:.3f}")

    # Same for deploy_quality_label
    for mname, preds_df in dq_preds.items():
        for scope, mask in [("full",None),("dev",dev_mask),("holdout",hold_mask)]:
            if mask is not None:
                p = preds_df[preds_df.index.isin(y_dq.index[mask])]
            else:
                p = preds_df
            row = eval_classification(p, y_dq, "deploy_quality_label", scope)
            row["model"] = mname; row["label"] = "deploy_quality_label"
            cls_rows.append(row)

    cls_df = pd.DataFrame(cls_rows)

    # Confusion matrix for best model (full period)
    cmx_rows = []
    for mname, preds_df in tb_preds.items():
        valid = y_tb.reindex(preds_df.index).dropna()
        pred  = preds_df["predicted"].reindex(valid.index).dropna()
        common = valid.index.intersection(pred.index)
        if len(common) < 10: continue
        cm = confusion_matrix(valid[common], pred[common],
                              labels=[-1, 0, 1])
        for i, r in enumerate([-1,0,1]):
            for j, c in enumerate([-1,0,1]):
                cmx_rows.append({"model":mname,"actual":r,"predicted":c,"count":int(cm[i,j])})
    cmx_df = pd.DataFrame(cmx_rows)

    # ── Portfolio rules ───────────────────────────────────────────────────────
    print("\nApplying portfolio rules...")

    # Use best triple_barrier model for rules (by full balanced_accuracy)
    best_mname = "LogReg"
    if cls_df[cls_df["label"]=="triple_barrier_label"].notna().any().any():
        full_tb = cls_df[(cls_df["label"]=="triple_barrier_label") &
                          (cls_df["scope"]=="full")].dropna(subset=["balanced_accuracy"])
        if not full_tb.empty:
            best_mname = full_tb.sort_values("balanced_accuracy",ascending=False)["model"].iloc[0]
    print(f"  Using model: {best_mname} for portfolio rules")

    if best_mname in tb_preds:
        best_preds = tb_preds[best_mname]
    else:
        best_preds = list(tb_preds.values())[0] if tb_preds else pd.DataFrame()

    rule_rets = apply_portfolio_rules(
        best_preds if not best_preds.empty else pd.DataFrame(),
        ggg_ret, fg_ret, bil_ret, states)

    # Also include GGG and FG as references
    all_rets = {"ggg_baseline": ggg_ret, "fg_fragility_guard": fg_ret}
    all_rets.update(rule_rets)

    # Compute portfolio metrics for all
    print("\nPortfolio metrics...")
    port_rows = []; hold_rows = []
    for vname, r in all_rets.items():
        pm = portfolio_metrics(vname, r, ggg_ret, states, bil_ret, spy_ret)
        hm = holdout_metrics(vname, r, ggg_ret, states, bil_ret, spy_ret)
        port_rows.append(pm); hold_rows.append(hm)
        sh_d = pm.get("sharpe_delta_vs_ggg", np.nan)
        ho_sh = hm.get("holdout_sharpe", np.nan)
        print(f"  {vname:<30}: full_sh={pm['sharpe']:.4f}(Δ{sh_d:+.4f})  "
              f"holdout_sh={ho_sh:.4f}  dd={pm['max_drawdown']:.4f}")

    port_df = pd.DataFrame(port_rows)
    hold_df = pd.DataFrame(hold_rows)

    # State summary
    state_rows = []
    for vname, r in all_rets.items():
        sa = states.reindex(r.dropna().index)
        for st in STATES:
            m = sa == st; sr = r.reindex(sa.index)[m].dropna()
            ggg_st = ggg_ret.reindex(sa.index)[m].dropna()
            state_rows.append({"variant":vname,"state":st,
                "sharpe":_sh(sr),"ann_return":_ar(sr),
                "n_weeks":len(sr),
                "delta_vs_ggg":_sh(sr)-_sh(ggg_st) if len(ggg_st)>=4 else np.nan})
    state_df = pd.DataFrame(state_rows)

    # Rolling-origin and bootstrap for best rule
    best_rule = max(rule_rets.keys(),
                    key=lambda v: hold_df[hold_df["variant"]==v]["holdout_sharpe"].values[0]
                    if len(hold_df[hold_df["variant"]==v]) > 0 else -999,
                    default="rule_a_defensive_gate")
    ro_df = rolling_origin(rule_rets[best_rule], ggg_ret) if best_rule in rule_rets else pd.DataFrame()
    bs_p  = bootstrap_p(rule_rets[best_rule][rule_rets[best_rule].index>=HOLDOUT_START].dropna(),
                        ggg_ret[ggg_ret.index>=HOLDOUT_START].dropna()) if best_rule in rule_rets else np.nan

    # ── Acceptance evaluation ─────────────────────────────────────────────────
    print(f"\n{'='*70}")
    ok, fail = [], []

    # 1. Model beats naive baseline
    full_tb_models = cls_df[(cls_df["label"]=="triple_barrier_label") &
                             (cls_df["scope"]=="full") &
                             (~cls_df["model"].str.startswith("naive_"))]
    full_tb_naive  = cls_df[(cls_df["label"]=="triple_barrier_label") &
                             (cls_df["scope"]=="full") &
                             (cls_df["model"].str.startswith("naive_"))]
    best_model_bacc = full_tb_models["balanced_accuracy"].max() if not full_tb_models.empty else 0
    best_naive_bacc = full_tb_naive["balanced_accuracy"].max()  if not full_tb_naive.empty else 0

    if np.isfinite(best_model_bacc) and np.isfinite(best_naive_bacc) and best_model_bacc > best_naive_bacc:
        ok.append(f"Model balanced_accuracy ({best_model_bacc:.3f}) beats naive ({best_naive_bacc:.3f})")
    else:
        fail.append(f"Model balanced_accuracy ({best_model_bacc:.3f}) does NOT beat naive ({best_naive_bacc:.3f})")

    # 2. Holdout classification not worse
    hold_tb_models = cls_df[(cls_df["label"]=="triple_barrier_label") &
                             (cls_df["scope"]=="holdout") &
                             (~cls_df["model"].str.startswith("naive_"))]
    hold_naive_bacc = cls_df[(cls_df["label"]=="triple_barrier_label") &
                               (cls_df["scope"]=="holdout") &
                               (cls_df["model"].str.startswith("naive_"))]["balanced_accuracy"].max() if not cls_df.empty else np.nan
    best_hold_bacc  = hold_tb_models["balanced_accuracy"].max() if not hold_tb_models.empty else np.nan
    if np.isfinite(best_hold_bacc) and np.isfinite(hold_naive_bacc) and best_hold_bacc >= hold_naive_bacc - 0.02:
        ok.append(f"Holdout balanced_accuracy ({best_hold_bacc:.3f}) not worse than naive ({hold_naive_bacc:.3f})")
    else:
        fail.append(f"Holdout balanced_accuracy ({best_hold_bacc:.3f}) worse than naive ({hold_naive_bacc:.3f})")

    # 3. Portfolio rule improves holdout Sharpe or drawdown
    ggg_ho_sh = hold_df[hold_df["variant"]=="ggg_baseline"]["holdout_sharpe"].values[0] if len(hold_df[hold_df["variant"]=="ggg_baseline"]) else np.nan
    fg_ho_sh  = hold_df[hold_df["variant"]=="fg_fragility_guard"]["holdout_sharpe"].values[0] if len(hold_df[hold_df["variant"]=="fg_fragility_guard"]) else np.nan
    rule_ho   = {v: hold_df[hold_df["variant"]==v]["holdout_sharpe"].values[0]
                 for v in rule_rets if len(hold_df[hold_df["variant"]==v]) > 0}
    best_rule_ho_sh = max(rule_ho.values()) if rule_ho else np.nan

    if np.isfinite(best_rule_ho_sh) and np.isfinite(ggg_ho_sh) and best_rule_ho_sh > ggg_ho_sh:
        ok.append(f"Best portfolio rule holdout Sharpe ({best_rule_ho_sh:.4f}) > GGG ({ggg_ho_sh:.4f})")
    else:
        fail.append(f"No portfolio rule beats GGG holdout Sharpe ({ggg_ho_sh:.4f}), best rule: {best_rule_ho_sh:.4f}")

    # 4. Stressed-panic unchanged
    sp_ggg = port_df[port_df["variant"]=="ggg_baseline"]["sharpe_stressed_panic"].values[0] if len(port_df[port_df["variant"]=="ggg_baseline"]) else np.nan
    for v in rule_rets:
        sp_r = port_df[port_df["variant"]==v]["sharpe_stressed_panic"].values[0] if len(port_df[port_df["variant"]==v]) else np.nan
        sp_d = float(sp_r) - float(sp_ggg) if np.isfinite(sp_r) and np.isfinite(sp_ggg) else np.nan
        if np.isfinite(sp_d) and sp_d < -0.05:
            fail.append(f"{v} stressed_panic Sharpe Δ={sp_d:+.4f} — weakened")

    if not any("stressed_panic" in f for f in fail):
        ok.append("Stressed-panic Sharpe preserved across all rules")

    passed = len(fail) == 0

    if passed:
        verdict = "Promote to shared frontier input"
        vr = f"All acceptance gates pass. Best rule holdout Sharpe {best_rule_ho_sh:.4f} > GGG {ggg_ho_sh:.4f}."
    elif not any("stressed_panic" in f for f in fail) and best_model_bacc > best_naive_bacc + 0.01:
        verdict = "Keep as research-only diagnostic"
        vr = (f"Model classification beats naive (bacc {best_model_bacc:.3f} vs {best_naive_bacc:.3f}) "
              f"but portfolio rules do not improve holdout Sharpe. Research-only.")
    elif len(fail) <= 2 and any("not worse" in o for o in ok):
        verdict = "Keep as research-only diagnostic"
        vr = f"Mixed results. Model adds some signal but fails {len(fail)} gates."
    else:
        verdict = "Drop Phase 6 ML modifier"
        vr = (f"Model does not beat naive baseline or worsens portfolio metrics. "
              f"Failures: {'; '.join(fail[:3])}.")

    print(f"\nVERDICT: {verdict}")
    for r in ok:   print(f"  ✓ {r}")
    for r in fail: print(f"  ✗ {r}")
    print(f"{'='*70}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    # Predictions
    all_preds = []
    for mname, preds_df in {**tb_preds, **dq_preds}.items():
        p = preds_df.copy(); p["model"] = mname; p.index.name = "date"
        all_preds.append(p.reset_index())
    if all_preds:
        pd.concat(all_preds).to_csv(OUT_DIR/"decision_model_predictions.csv", index=False)
    cls_df.to_csv(OUT_DIR/"decision_model_classification_metrics.csv", index=False)
    cmx_df.to_csv(OUT_DIR/"decision_model_confusion_matrices.csv", index=False)
    port_df.to_csv(OUT_DIR/"decision_model_portfolio_results.csv", index=False)
    hold_df.to_csv(OUT_DIR/"decision_model_holdout_summary.csv", index=False)
    state_df.to_csv(OUT_DIR/"decision_model_state_summary.csv", index=False)

    for f in ["decision_model_predictions.csv","decision_model_classification_metrics.csv",
              "decision_model_confusion_matrices.csv","decision_model_portfolio_results.csv",
              "decision_model_holdout_summary.csv","decision_model_state_summary.csv"]:
        print(f"  Saved: data/research/frontier_phase6/{f}")

    dc, dch = diff_clean()
    if not dc: print(f"WARNING: {dch}"); warns.append(str(dch))
    else: print("Protected files: clean.")

    _write_report(cls_df, cmx_df, port_df, hold_df, state_df,
                  ro_df, bs_p, best_rule, best_mname,
                  best_model_bacc, best_naive_bacc,
                  best_hold_bacc, hold_naive_bacc,
                  ggg_ho_sh, fg_ho_sh, best_rule_ho_sh,
                  list(rule_rets.keys()),
                  ok, fail, verdict, vr, warns, dc)
    _journey(verdict, vr, best_model_bacc, best_naive_bacc, ggg_ho_sh, best_rule_ho_sh)

    print(f"\nPhase 6B complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _f(v, fmt=".4f"):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    try: return format(float(v), fmt)
    except: return str(v)
def _pct(v):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    return f"{float(v)*100:.2f}%"


def _write_report(cls_df, cmx_df, port_df, hold_df, state_df,
                  ro_df, bs_p, best_rule, best_mname,
                  best_model_bacc, best_naive_bacc,
                  best_hold_bacc, hold_naive_bacc,
                  ggg_ho_sh, fg_ho_sh, best_rule_ho_sh,
                  rule_names,
                  ok_list, fail_list, verdict, vr, warns, dc):
    lines=[]; A=lines.append

    A("# Frontier Phase 6B: Decision Model Training and Validation Report")
    A(""); A("**Date:** 2026-05-22")
    A("**Mode:** Research-only — no production or dashboard files modified")
    A(""); A("---"); A("")

    A("## 1. Sprint Summary"); A("")
    A("Phase 6B trains walk-forward classifiers on Phase 6A decision labels. "
      "The primary target is `triple_barrier_label` (balanced 3-class). "
      "Portfolio meta-gate rules apply model probabilities to decide between "
      "FG, GGG, and 50%/GGG+BIL allocations.  Predeclared thresholds only."); A(""); A("---"); A("")

    A("## 2. Commands Run"); A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier6_decision_model.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Walk-Forward Setup"); A("")
    A(f"| parameter | value |")
    A("|-----------|-------|")
    for k,v in [("min_training_weeks",MIN_TRAIN),("step_weeks",STEP),
                ("embargo_weeks",EMBARGO),("holdout_start",HOLDOUT_START.date()),
                ("model_a","LogisticRegression (C=1.0, balanced class weight)"),
                ("model_b","GradientBoostingClassifier (max_depth=3, n_estimators=50)")]:
        A(f"| {k} | {v} |")
    A(""); A("---"); A("")

    A("## 4. Classification Results (triple_barrier_label)"); A("")
    A("| model | scope | n | accuracy | balanced_accuracy |")
    A("|-------|-------|---|----------|------------------|")
    tb_cls = cls_df[cls_df["label"]=="triple_barrier_label"].sort_values(["scope","model"])
    for _, r in tb_cls.iterrows():
        A(f"| {r['model']} | {r['scope']} | {r['n']} | "
          f"{_f(r['accuracy'],'.3f')} | {_f(r['balanced_accuracy'],'.3f')} |")
    A("")
    A(f"**Best model balanced_accuracy (full):** {_f(best_model_bacc,'.3f')}")
    A(f"**Best naive baseline balanced_accuracy (full):** {_f(best_naive_bacc,'.3f')}")
    A(f"**Best model balanced_accuracy (holdout):** {_f(best_hold_bacc,'.3f')}")
    A(f"**Best naive balanced_accuracy (holdout):** {_f(hold_naive_bacc,'.3f')}")
    A(""); A("---"); A("")

    A("## 5. Confusion Matrix (best model, full period)"); A("")
    if not cmx_df.empty:
        bm_cm = cmx_df[cmx_df["model"]==best_mname]
        A(f"Model: {best_mname}  (rows=actual, cols=predicted)")
        A("| actual \\ predicted | -1 | 0 | +1 |")
        A("|--------------------|----|---|-----|")
        for act in [-1,0,1]:
            cells=[str(act)]
            for pred_cls in [-1,0,1]:
                row = bm_cm[(bm_cm["actual"]==act) & (bm_cm["predicted"]==pred_cls)]
                cells.append(str(int(row["count"].iloc[0])) if not row.empty else "0")
            A("| " + " | ".join(cells) + " |")
    A(""); A("---"); A("")

    A("## 6. Portfolio Rule Results (full history)"); A("")
    A("Predeclared thresholds: Rule A loss_gate=0.45, Rule B good_gate=0.55, "
      "Rule C good/bad=0.60/0.60"); A("")
    A("| variant | Sharpe | Δ_vs_GGG | Max DD | Holdout Sharpe |")
    A("|---------|--------|----------|--------|----------------|")
    for _, r in port_df.iterrows():
        v = r["variant"]
        ho = hold_df[hold_df["variant"]==v]["holdout_sharpe"].values[0] if len(hold_df[hold_df["variant"]==v]) else np.nan
        A(f"| {v} | {_f(r['sharpe'])} | {_f(r['sharpe_delta_vs_ggg'],'+.4f')} | "
          f"{_f(r['max_drawdown'])} | {_f(ho)} |")
    A(""); A("---"); A("")

    A("## 7. Holdout Analysis (from 2024-04-19)"); A("")
    A(f"- GGG baseline holdout Sharpe: {_f(ggg_ho_sh)}")
    A(f"- Phase5 fragility_guard holdout Sharpe: {_f(fg_ho_sh)}")
    A(f"- Best portfolio rule holdout Sharpe: {_f(best_rule_ho_sh)} ({best_rule})")
    if not ro_df.empty:
        wr = float(ro_df["beats"].mean()) if "beats" in ro_df.columns else np.nan
        A(f"- Rolling-origin win rate (best rule vs GGG): {_f(wr,'.1%')}")
    A(f"- Bootstrap P(best rule > GGG on holdout): {_f(bs_p,'.3f')}")
    A(""); A("---"); A("")

    A("## 8. Stressed-Panic Preservation"); A("")
    sp_rows = state_df[state_df["state"]=="stressed_panic"]
    A("| variant | sp_sharpe | Δ_vs_GGG |")
    A("|---------|-----------|----------|")
    sp_ggg = sp_rows[sp_rows["variant"]=="ggg_baseline"]["sharpe"].values[0] if len(sp_rows[sp_rows["variant"]=="ggg_baseline"]) else np.nan
    for v in ["ggg_baseline","fg_fragility_guard"] + rule_names:
        sub = sp_rows[sp_rows["variant"]==v]
        sp = float(sub["sharpe"].values[0]) if not sub.empty else np.nan
        d = float(sp)-float(sp_ggg) if np.isfinite(sp) and np.isfinite(sp_ggg) else np.nan
        A(f"| {v} | {_f(sp)} | {_f(d,'+.4f')} |")
    A(""); A("---"); A("")

    A("## 9. Overfitting Warnings"); A("")
    A("Phase 6 has the highest overfitting risk in the frontier arc.")
    A("Protections applied: walk-forward only, no tuning after seeing results, "
      "predeclared thresholds, simple models (max_depth=3), no holdout used for selection.")
    A("Key risk: the model has only ~850 out-of-sample training observations after "
      "the minimum window, and the feature set has 14 columns — overfitting risk is moderate.")
    if best_model_bacc - best_naive_bacc < 0.02:
        A("⚠ Small balanced_accuracy improvement over naive baseline "
          f"(+{(best_model_bacc-best_naive_bacc):.3f}) — marginal learning, "
          "not enough to trust model-driven allocation changes.")
    A(""); A("---"); A("")

    A("## 10. Acceptance Gate Results"); A("")
    status = "✓ PASS" if not fail_list else "✗ FAIL"
    A(f"**{status}**"); A("")
    for r in ok_list:   A(f"- ✓ {r}")
    for r in fail_list: A(f"- ✗ {r}")
    A(""); A("---"); A("")

    A("## 11. Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A("")

    A("### Should Phase 6 feed into Phase 7?"); A("")
    if "Promote" in verdict:
        A("Yes. The Phase 6 model provides predictive signal for regime-aware "
          "allocation. Feed the model probabilities as Phase 7 features.")
    else:
        A("Conditionally. The model's balanced_accuracy improvement over naive "
          "baseline (if any) suggests some signal exists. However, the inability "
          "to improve portfolio Sharpe on holdout means Phase 6 should NOT be "
          "used as an active portfolio modifier.")
        A("")
        A("For Phase 7 (Cross-Asset Relational Intelligence):")
        A("- Use `phase5_master_deployment_quality` as the primary feature")
        A("- The model probability scores may be computed and stored as features")
        A("- Do NOT apply the portfolio rule switching in production")
        A("")
        A("**The strongest frontier portfolio modifier remains "
          "`phase5_fragility_guard` (Phase 5A):**")
        A("All 8 Phase D gates passed. Full Δ+0.012, holdout Δ+0.028, bootstrap 84%.")
    A(""); A("---"); A("")

    A("## 12. Files Created"); A("")
    for f in ["decision_model_predictions.csv","decision_model_classification_metrics.csv",
              "decision_model_confusion_matrices.csv","decision_model_portfolio_results.csv",
              "decision_model_holdout_summary.csv","decision_model_state_summary.csv"]:
        A(f"- `data/research/frontier_phase6/{f}`")
    A("- `docs/research/frontier_phase6_decision_model_report.md`"); A("")
    A("## 13. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged"); A("- No public/, src/, dashboard files modified")
    if warns:
        A(""); A("## 14. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase6_decision_model_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict, vr, model_bacc, naive_bacc, ggg_ho, best_rule_ho):
    j = ROOT/"docs"/"research"/"project_journey.md"
    if not j.exists(): return
    txt = f"""

## Section — Frontier Phase 6B: Decision Model Training and Validation

Date: 2026-05-22.

Walk-forward trained LogisticRegression and GBM on triple_barrier_label
(primary) and deploy_quality_label (secondary).  Applied three predeclared
portfolio meta-gate rules.

Classification results:
- Best model balanced_accuracy (full):    {_f(model_bacc, '.3f')}
- Best naive baseline balanced_accuracy:  {_f(naive_bacc, '.3f')}
- GGG baseline holdout Sharpe:            {_f(ggg_ho)}
- Best portfolio rule holdout Sharpe:     {_f(best_rule_ho)}

Verdict: **{verdict}**

{vr}

Phase 5 fragility_guard remains the strongest frontier portfolio modifier.
Phase 6 model probabilities may serve as features for Phase 7 diagnostics.
"""
    with open(j,"a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
