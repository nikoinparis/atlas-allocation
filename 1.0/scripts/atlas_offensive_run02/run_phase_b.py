#!/usr/bin/env python3
"""R02 Phase B — label-stability benchmark: jump model (lambda in {1,2,4}) and
5-state Gaussian HMM vs the production 5-state engine.

Benchmark only (pre-registered): each label set drives the same expanding
state-conditional offense action rule; portfolio value computed net of
per-instrument costs on the dev window. Not a replacement decision.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from r02_lib import (
    OUT_DIR, SEED, WEEKS,
    R02Machinery, core_metrics, load_cost_vector, per_instrument_path,
)
from path1_path3_research_utils import normalize_to_cash
from moonshot_features import expanding_standardize

K = 5
LAMBDAS = [1.0, 2.0, 4.0]
FIRST_FIT = 260
REFIT_EVERY = 52
MIN_OBS_ACTION = 26
MULT_UP, MULT_DOWN = 1.10, 0.90


def kmeans_init(X: np.ndarray, k: int, rng: np.random.Generator, iters: int = 15) -> np.ndarray:
    centers = X[rng.choice(len(X), k, replace=False)].copy()
    for _ in range(iters):
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            if (lab == j).any():
                centers[j] = X[lab == j].mean(0)
    return centers


def fit_jump_model(X: np.ndarray, lam: float, rng: np.random.Generator, iters: int = 10) -> np.ndarray:
    """Transition-penalized clustering; returns centers."""
    centers = kmeans_init(X, K, rng)
    T = len(X)
    for _ in range(iters):
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)  # T x K
        cost = np.zeros((T, K))
        back = np.zeros((T, K), dtype=int)
        cost[0] = d[0]
        for t in range(1, T):
            prev = cost[t - 1]
            stay = prev
            switch = prev.min() + lam
            best_prev = prev.argmin()
            for s in range(K):
                if stay[s] <= switch:
                    cost[t, s] = d[t, s] + stay[s]
                    back[t, s] = s
                else:
                    cost[t, s] = d[t, s] + switch
                    back[t, s] = best_prev
        lab = np.zeros(T, dtype=int)
        lab[-1] = cost[-1].argmin()
        for t in range(T - 2, -1, -1):
            lab[t] = back[t + 1, lab[t + 1]]
        new_centers = centers.copy()
        for j in range(K):
            if (lab == j).any():
                new_centers[j] = X[lab == j].mean(0)
        if np.allclose(new_centers, centers, atol=1e-10):
            centers = new_centers
            break
        centers = new_centers
    return centers


def walk_forward_jump(X: np.ndarray, lam: float, rng: np.random.Generator) -> np.ndarray:
    T = len(X)
    labels = np.full(T, -1)
    centers = None
    prev_state = None
    for t in range(FIRST_FIT, T):
        if (t - FIRST_FIT) % REFIT_EVERY == 0:
            centers = fit_jump_model(X[:t], lam, rng)
        d = ((X[t] - centers) ** 2).sum(-1)
        if prev_state is not None:
            pen = np.full(K, lam)
            pen[prev_state] = 0.0
            d = d + pen
        labels[t] = int(d.argmin())
        prev_state = labels[t]
    return labels


def fit_hmm(X: np.ndarray, rng: np.random.Generator, iters: int = 30):
    """Diagonal Gaussian HMM via EM (log-space). Returns (pi, A, mu, var)."""
    T, D = X.shape
    centers = kmeans_init(X, K, rng)
    d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
    lab = d.argmin(1)
    mu = centers.copy()
    var = np.array([X[lab == j].var(0) + 1e-3 if (lab == j).sum() > 1 else np.ones(D) for j in range(K)])
    A = np.full((K, K), 0.02 / (K - 1))
    np.fill_diagonal(A, 0.98)
    pi = np.full(K, 1.0 / K)
    for _ in range(iters):
        logb = -0.5 * (((X[:, None, :] - mu[None]) ** 2 / var[None]).sum(-1)
                       + np.log(2 * np.pi * var).sum(-1)[None])
        la = np.zeros((T, K))
        la[0] = np.log(pi + 1e-300) + logb[0]
        logA = np.log(A + 1e-300)
        for t in range(1, T):
            la[t] = logb[t] + np.logaddexp.reduce(la[t - 1][:, None] + logA, axis=0)
        lb = np.zeros((T, K))
        for t in range(T - 2, -1, -1):
            lb[t] = np.logaddexp.reduce(logA + (logb[t + 1] + lb[t + 1])[None, :], axis=1)
        lg = la + lb
        lg -= np.logaddexp.reduce(lg, axis=1, keepdims=True)
        g = np.exp(lg)
        xi_num = np.zeros((K, K))
        for t in range(T - 1):
            m = la[t][:, None] + logA + (logb[t + 1] + lb[t + 1])[None, :]
            m -= np.logaddexp.reduce(m.ravel())
            xi_num += np.exp(m)
        pi = g[0] / g[0].sum()
        A = xi_num / np.maximum(xi_num.sum(1, keepdims=True), 1e-300)
        w = g.sum(0)
        mu = (g.T @ X) / np.maximum(w[:, None], 1e-300)
        var = np.array([((X - mu[j]) ** 2 * g[:, [j]]).sum(0) / max(w[j], 1e-300) for j in range(K)]) + 1e-4
    return pi, A, mu, var


def walk_forward_hmm(X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    T = len(X)
    labels = np.full(T, -1)
    params = None
    log_alpha = None
    for t in range(FIRST_FIT, T):
        if (t - FIRST_FIT) % REFIT_EVERY == 0:
            params = fit_hmm(X[:t], rng)
            pi, A, mu, var = params
            # rebuild filtered recursion up to t-1 with the new params (causal)
            logA = np.log(A + 1e-300)
            log_alpha = np.log(pi + 1e-300) + _logb_row(X[0], mu, var)
            for u in range(1, t):
                log_alpha = _logb_row(X[u], mu, var) + np.logaddexp.reduce(log_alpha[:, None] + logA, axis=0)
                log_alpha -= np.logaddexp.reduce(log_alpha)
        pi, A, mu, var = params
        logA = np.log(A + 1e-300)
        log_alpha = _logb_row(X[t], mu, var) + np.logaddexp.reduce(log_alpha[:, None] + logA, axis=0)
        log_alpha -= np.logaddexp.reduce(log_alpha)
        labels[t] = int(log_alpha.argmax())
    return labels


def _logb_row(x: np.ndarray, mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    return -0.5 * (((x - mu) ** 2 / var).sum(-1) + np.log(2 * np.pi * var).sum(-1))


def label_stats(labels: pd.Series) -> dict:
    lab = labels[labels >= 0] if labels.dtype != object else labels.dropna()
    changes = (lab != lab.shift()).sum() - 1
    years = len(lab) / WEEKS
    spells = (lab != lab.shift()).cumsum()
    spell_len = lab.groupby(spells).size()
    return {"transitions_per_year": float(changes / years), "median_spell_weeks": float(spell_len.median()),
            "n_weeks_labeled": int(len(lab))}


def action_rule_path(mach: R02Machinery, labels: pd.Series, cost_vec: pd.Series) -> pd.DataFrame:
    """Common expanding state-conditional offense action rule (pre-registered)."""
    off = [c for c in mach.nwr.columns if c in mach.offense_cols]
    excess = mach.nwr[off].mean(axis=1) - mach.nwr["BIL"].fillna(0.0)  # realized at t+1
    lab = labels.reindex(mach.index)
    mult = pd.Series(1.0, index=mach.index)
    hist: dict = {}
    lab_vals = lab.to_numpy()
    exc_vals = excess.to_numpy()
    for t in range(len(mach.index)):
        s = lab_vals[t]
        if s is not None and s == s and s != -1:
            h = hist.get(s)
            if h is not None and h[1] >= MIN_OBS_ACTION:
                mult.iloc[t] = MULT_UP if h[0] / h[1] > 0 else MULT_DOWN
        # update history with week t-1's realized excess (known at t close -> usable at t+1)
        if t >= 1:
            s_prev = lab_vals[t - 1]
            e_prev = exc_vals[t - 1]
            if s_prev is not None and s_prev == s_prev and s_prev != -1 and np.isfinite(e_prev):
                a, n = hist.get(s_prev, (0.0, 0))
                hist[s_prev] = (a + e_prev, n + 1)
    w = mach.base_weights.copy()
    w[mach.offense_cols] = w[mach.offense_cols].mul(mult, axis=0)
    w = normalize_to_cash(w)
    return per_instrument_path(w, mach.nwr, cost_vec)


def main() -> int:
    t0 = time.time()
    mach = R02Machinery()
    rng = np.random.default_rng(SEED)
    cost1x = load_cost_vector(1.0)
    spy_next = mach.nwr["SPY"]

    Z = expanding_standardize(mach.feats).clip(-5, 5).fillna(0.0)
    X = Z.to_numpy(dtype=float)
    print(f"Feature matrix: {X.shape}")

    arms: dict[str, pd.Series] = {
        "production_5state": mach.states.copy(),
    }
    for lam in LAMBDAS:
        print(f"Fitting walk-forward jump model lambda={lam} ...")
        labs = walk_forward_jump(X, lam, rng)
        arms[f"jump_lambda{int(lam)}"] = pd.Series(labs, index=mach.index)
    print("Fitting walk-forward HMM ...")
    labs = walk_forward_hmm(X, rng)
    arms["hmm_5state"] = pd.Series(labs, index=mach.index)

    base_path = per_instrument_path(mach.base_weights, mach.nwr, cost1x)
    base_m = core_metrics(base_path, spy_next)
    rows = [{"arm": "ggg_base_no_action", **{k: np.nan for k in ("transitions_per_year", "median_spell_weeks", "n_weeks_labeled")},
             **base_m}]
    for name, labels in arms.items():
        stats = label_stats(labels if labels.dtype == object else labels.astype(int))
        path = action_rule_path(mach, labels, cost1x)
        m = core_metrics(path, spy_next)
        rows.append({"arm": name, **stats, **m,
                     "delta_cagr_vs_base": m["net_cagr"] - base_m["net_cagr"],
                     "delta_logg_vs_base": m["log_growth"] - base_m["log_growth"]})
        print(f"{name}: trans/yr {stats['transitions_per_year']:.1f}  spell {stats['median_spell_weeks']:.0f}w  "
              f"dCAGR {m['net_cagr'] - base_m['net_cagr']:+.4%}")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "phase_b_label_benchmark.csv", index=False)
    (OUT_DIR / "phase_b_manifest.json").write_text(json.dumps(
        {"K": K, "lambdas": LAMBDAS, "first_fit": FIRST_FIT, "refit_every": REFIT_EVERY,
         "seed": SEED, "runtime_s": round(time.time() - t0, 1)}, indent=2))
    print(f"Phase B done ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
