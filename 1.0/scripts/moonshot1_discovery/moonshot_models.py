"""Model components for the moonshot discovery sprint (numpy only).

Everything here is walk-forward by construction:
    * kNN analog engine: analogs restricted to weeks <= t - embargo.
    * Ridge baseline: expanding refit every `refit_every` weeks, same embargo.
    * k-means state discovery: centroids refit every `refit_every` weeks on
      past rows only; cluster actions from past targets only.
    * PBI multiplier: pure rule on the (already shifted) feature panel.

Capacity is deliberately tiny: ~1,000 usable weeks cannot support more.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EMBARGO_WEEKS = 8          # > target horizon (4w) to kill label overlap leakage
MIN_TRAIN_WEEKS = 156
AMPLITUDE = 0.08           # matches production R2A amplitude for comparability


# ── M1: panic-but-improving rule ─────────────────────────────────────────────


def pbi_multiplier(
    states: pd.Series,
    pbi: pd.DataFrame,
    *,
    count_gate: int = 2,
    mult_partial: float = 1.15,
    mult_full: float = 1.30,
    dd_context: float = -0.10,
) -> pd.Series:
    """Offense multiplier active ONLY inside stressed_panic weeks.

    Never below 1.0: defense is only ever left alone or nudged toward offense
    when the improvement composite confirms. Everything outside stressed_panic
    is exactly 1.0, the complement of every prior overlay in this project.
    """

    mult = pd.Series(1.0, index=states.index)
    sp = states.astype(str).eq("stressed_panic")
    deep = pbi["deep_dd_context"].reindex(states.index).fillna(0.0) > 0
    count = pbi["confirm_count"].reindex(states.index)
    # deep_dd_context recomputed against the configurable threshold:
    if dd_context != -0.10:
        deep = pbi["market_drawdown_ctx"].reindex(states.index) <= dd_context
    fire_partial = sp & deep & (count >= count_gate) & (count < 3)
    fire_full = sp & deep & (count >= 3)
    if count_gate >= 3:
        fire_partial &= False
    mult[fire_partial] = mult_partial
    mult[fire_full] = mult_full
    return mult


# ── M2: kNN analog decision engine ───────────────────────────────────────────


def knn_analog_predictions(
    z: pd.DataFrame,
    target: pd.Series,
    *,
    k: int = 25,
    embargo: int = EMBARGO_WEEKS,
    min_train: int = MIN_TRAIN_WEEKS,
) -> pd.Series:
    """Walk-forward kNN: mean target of the k nearest past weeks."""

    cols = z.columns
    X = z[cols].to_numpy(dtype=float)
    y = target.to_numpy(dtype=float)
    n = len(z)
    preds = np.full(n, np.nan)
    valid_row = ~np.isnan(X).any(axis=1)
    for t in range(min_train, n):
        if not valid_row[t]:
            continue
        hist_end = t - embargo
        if hist_end < min_train // 2:
            continue
        mask = valid_row[:hist_end] & ~np.isnan(y[:hist_end])
        idx = np.where(mask)[0]
        if len(idx) < k * 2:
            continue
        d = np.sqrt(((X[idx] - X[t]) ** 2).sum(axis=1))
        nearest = idx[np.argsort(d)[:k]]
        preds[t] = float(np.mean(y[nearest]))
    return pd.Series(preds, index=z.index)


def ridge_predictions(
    z: pd.DataFrame,
    target: pd.Series,
    *,
    lam: float = 10.0,
    refit_every: int = 26,
    embargo: int = EMBARGO_WEEKS,
    min_train: int = MIN_TRAIN_WEEKS,
) -> pd.Series:
    """Walk-forward ridge regression baseline on the same features/target."""

    X = z.to_numpy(dtype=float)
    y = target.to_numpy(dtype=float)
    n, p = X.shape
    preds = np.full(n, np.nan)
    valid_row = ~np.isnan(X).any(axis=1)
    beta = None
    for t in range(min_train, n):
        if (t - min_train) % refit_every == 0:
            hist_end = t - embargo
            mask = valid_row[:hist_end] & ~np.isnan(y[:hist_end])
            if mask.sum() >= min_train // 2:
                Xh, yh = X[:hist_end][mask], y[:hist_end][mask]
                A = Xh.T @ Xh + lam * np.eye(p)
                beta = np.linalg.solve(A, Xh.T @ yh)
        if beta is not None and valid_row[t]:
            preds[t] = float(X[t] @ beta)
    return pd.Series(preds, index=z.index)


def predictions_to_multiplier(
    preds: pd.Series,
    target: pd.Series,
    states: pd.Series,
    *,
    amplitude: float = AMPLITUDE,
    embargo: int = EMBARGO_WEEKS,
) -> pd.Series:
    """Map raw predictions to a bounded offense multiplier, walk-forward scaled.

    Scale = expanding std of the *target* lagged by the embargo, so the
    normalization itself cannot leak. stressed_panic is forced to 1.0 (M1
    owns that state; M2/M3 are evaluated on the same domain as the R2A rule).
    """

    sigma = target.expanding(min_periods=52).std(ddof=1).shift(embargo)
    z = (preds / (2.0 * sigma)).clip(-1.0, 1.0)
    mult = 1.0 + amplitude * z.fillna(0.0)
    mult[states.astype(str).eq("stressed_panic")] = 1.0
    return mult


# ── M3: walk-forward k-means state discovery ─────────────────────────────────


def _kmeans_fit(X: np.ndarray, k: int, rng: np.random.Generator, iters: int = 25) -> np.ndarray:
    # k-means++ style seeding
    centroids = [X[rng.integers(len(X))]]
    for _ in range(k - 1):
        d2 = np.min(((X[:, None, :] - np.array(centroids)[None, :, :]) ** 2).sum(-1), axis=1)
        prob = d2 / d2.sum() if d2.sum() > 0 else None
        centroids.append(X[rng.choice(len(X), p=prob)] if prob is not None else X[rng.integers(len(X))])
    C = np.array(centroids)
    for _ in range(iters):
        assign = np.argmin(((X[:, None, :] - C[None, :, :]) ** 2).sum(-1), axis=1)
        for j in range(k):
            pts = X[assign == j]
            if len(pts):
                C[j] = pts.mean(axis=0)
    return C


def kmeans_state_multiplier(
    z: pd.DataFrame,
    target: pd.Series,
    states: pd.Series,
    *,
    k: int = 7,
    refit_every: int = 52,
    embargo: int = EMBARGO_WEEKS,
    min_train: int = MIN_TRAIN_WEEKS,
    amplitude: float = AMPLITUDE,
    seed: int = 20260707,
    action_permutation: np.ndarray | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Walk-forward learned-state multiplier. Returns (multiplier, cluster_id).

    `action_permutation` lets the null test scramble which cluster gets which
    action while keeping the state assignments identical.
    """

    X = z.to_numpy(dtype=float)
    y = target.to_numpy(dtype=float)
    n = len(z)
    valid_row = ~np.isnan(X).any(axis=1)
    rng = np.random.default_rng(seed)
    mult = np.ones(n)
    cluster_id = np.full(n, -1)
    C = None
    for t in range(min_train, n):
        if (t - min_train) % refit_every == 0:
            hist_end = t - embargo
            mask = valid_row[:hist_end]
            if mask.sum() >= min_train // 2:
                C = _kmeans_fit(X[:hist_end][mask], k, rng)
                # cluster actions from past targets only
                assign_h = np.argmin(((X[:hist_end][mask][:, None, :] - C[None, :, :]) ** 2).sum(-1), axis=1)
                yh = y[:hist_end][mask]
                sigma = np.nanstd(yh, ddof=1)
                actions = np.zeros(k)
                for j in range(k):
                    yj = yh[(assign_h == j) & ~np.isnan(yh)]
                    if len(yj) >= 10 and sigma > 0:
                        actions[j] = np.clip(np.mean(yj) / (2.0 * sigma), -1.0, 1.0)
                if action_permutation is not None:
                    actions = actions[action_permutation]
        if C is not None and valid_row[t]:
            j = int(np.argmin(((C - X[t]) ** 2).sum(-1)))
            cluster_id[t] = j
            mult[t] = 1.0 + amplitude * actions[j]
    out = pd.Series(mult, index=z.index)
    out[states.astype(str).eq("stressed_panic")] = 1.0
    return out, pd.Series(cluster_id, index=z.index)


# ── M4: walk-forward objective-driven alpha selection ────────────────────────


def r2a_scale_with_alpha(r2a: pd.Series, leadership: pd.Series, states: pd.Series, alpha: float) -> pd.Series:
    """Reimplementation of the production scale with a configurable alpha."""

    q = r2a.clip(-1.0, 1.0).fillna(0.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    not_sp = states.astype(str).ne("stressed_panic")
    scale.loc[not_sp] = 1.0 + alpha * q.loc[not_sp]
    crowded = leadership.gt(0.50)
    scale.loc[crowded & not_sp] = scale.loc[crowded & not_sp].clip(upper=1.0)
    scale.loc[~not_sp] = 1.0
    return scale


def objective_value(net: pd.Series, objective: str) -> float:
    net = net.dropna()
    if len(net) < 52:
        return -np.inf
    wealth = float((1 + net).prod())
    cagr = wealth ** (52.0 / len(net)) - 1.0 if wealth > 0 else -1.0
    vol = float(net.std(ddof=1)) * np.sqrt(52.0)
    sharpe = cagr / vol if vol > 0 else -np.inf
    w = (1 + net).cumprod()
    maxdd = float((w / w.cummax() - 1.0).min())
    tail = net[net <= net.quantile(0.05)]
    cvar = float(tail.mean()) if len(tail) else 0.0
    if objective == "sharpe":
        return sharpe
    if objective == "tail_utility":
        return cagr - 5.0 * abs(cvar) - 2.0 * max(0.0, abs(maxdd) - 0.12)
    if objective == "calmar_blend":
        calmar = cagr / abs(maxdd) if maxdd < 0 else 0.0
        return 0.5 * sharpe + 0.5 * calmar
    raise ValueError(objective)


def adaptive_alpha_path(
    alpha_paths: dict[float, pd.DataFrame],
    alpha_weights: dict[float, pd.DataFrame],
    objective: str,
    *,
    refit_every: int = 26,
    min_train: int = MIN_TRAIN_WEEKS,
    cost_bps: float = 10.0,
) -> tuple[pd.Series, pd.Series]:
    """Splice per-alpha net returns by walk-forward objective selection.

    Charges an explicit splice cost using the true one-way turnover between
    the outgoing and incoming alpha weight rows at each switch date.
    Returns (net_return_series, chosen_alpha_series).
    """

    alphas = sorted(alpha_paths)
    nets = {a: alpha_paths[a].set_index("Date")["net_return"] for a in alphas}
    index = nets[alphas[0]].index
    chosen = pd.Series(np.nan, index=index)
    out = pd.Series(np.nan, index=index)
    current = None
    for t in range(min_train, len(index), refit_every):
        past = index[:t]
        best_a, best_v = None, -np.inf
        for a in alphas:
            v = objective_value(nets[a].loc[past], objective)
            if v > best_v:
                best_a, best_v = a, v
        block = index[t : t + refit_every]
        out.loc[block] = nets[best_a].loc[block]
        chosen.loc[block] = best_a
        if current is not None and best_a != current:
            w_old = alpha_weights[current].loc[block[0]]
            w_new = alpha_weights[best_a].loc[block[0]]
            splice_cost = 0.5 * float((w_new - w_old).abs().sum()) * cost_bps / 1e4
            out.loc[block[0]] -= splice_cost
        current = best_a
    return out, chosen
