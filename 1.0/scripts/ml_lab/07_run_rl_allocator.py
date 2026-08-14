#!/usr/bin/env python3
"""
Phase MLX-8: deep reinforcement learning ETF allocator.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import gymnasium as _GYMNASIUM_BASE
except Exception:
    _GYMNASIUM_BASE = None


ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
SEQUENCE_DIR = ROOT / "data" / "research" / "ml_lab" / "sequence_models"
TRANSFORMER_DIR = ROOT / "data" / "research" / "ml_lab" / "transformers"
META_DIR = ROOT / "data" / "research" / "ml_lab" / "meta_labeling"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "reinforcement_learning"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"
SEQUENCE_BACKTEST_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_PREDICTIONS_IN = SEQUENCE_DIR / "sequence_predictions.parquet"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
MLX5C_SUMMARY_IN = SEQUENCE_DIR / "multiseed_walkforward" / "sequence_multiseed_summary.json"
TRANSFORMER_BACKTEST_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_PREDICTIONS_IN = TRANSFORMER_DIR / "transformer_predictions.parquet"
META_RETURNS_IN = META_DIR / "meta_label_strategy_returns.csv"
META_SUMMARY_IN = META_DIR / "meta_label_strategy_summary.csv"

TRAINING_LOG_OUT = OUTPUT_DIR / "rl_training_log.csv"
POLICY_PREDICTIONS_OUT = OUTPUT_DIR / "rl_policy_predictions.parquet"
POLICY_WEIGHTS_OUT = OUTPUT_DIR / "rl_policy_weights.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "rl_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "rl_summary.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "rl_strategy_comparison.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "rl_state_by_state.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "rl_exposure_audit.csv"
REWARD_DEFINITIONS_OUT = OUTPUT_DIR / "rl_reward_definitions.json"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "rl_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "rl_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_reinforcement_learning_notes.md"

TARGET_COLUMNS = {
    "forward_return_4w",
    "forward_return_13w",
    "forward_rank_4w",
    "forward_rank_13w",
    "beats_SPY_4w",
    "beats_BIL_4w",
    "positive_forward_4w",
    "top_quintile_forward_4w",
}
TARGET_LIKE_PREFIXES = ("forward_", "future_", "next_", "beats_", "top_quintile", "positive_forward")
DEFAULT_COST_BPS = 10.0
TOTAL_TIMESTEPS = 25_000
REWARD_VARIANTS = ("return_only", "turnover_penalized", "risk_aware", "defensive_regime_aware")
SEEDS = (0, 1, 2)
SAFE_ASSETS = {"BIL", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD"}
GYM_ENV_BASE = _GYMNASIUM_BASE.Env if _GYMNASIUM_BASE is not None else object


@dataclass(frozen=True)
class RLRun:
    algorithm: str
    reward_variant: str
    seed: int
    total_timesteps: int

    @property
    def strategy_name(self) -> str:
        return f"{self.algorithm.lower()}__{self.reward_variant}__seed{self.seed}__softmax_long_only"


def warn(message: str, warnings_list: list[str]) -> None:
    warnings_list.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def package_status() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in ("gymnasium", "stable_baselines3", "torch"):
        try:
            module = __import__(name)
            out[name] = {"available": True, "version": getattr(module, "__version__", None)}
        except Exception as exc:
            out[name] = {"available": False, "version": None, "error": f"{type(exc).__name__}: {exc}"}
    return out


def load_mlx5_module() -> Any:
    path = ROOT / "scripts" / "ml_lab" / "04_run_sequence_models.py"
    spec = importlib.util.spec_from_file_location("mlx5_sequence_models", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import MLX-5 helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def split_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    parsed = pd.to_datetime(dates)
    index = dates.index if isinstance(dates, pd.Series) else pd.DatetimeIndex(parsed)
    s = pd.Series(parsed, index=index)
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
    return out


def max_drawdown(returns: pd.Series) -> float:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {"annual_return": np.nan, "annual_volatility": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "calmar": np.nan, "cvar_5": np.nan, "average_turnover": np.nan, "annual_cost_drag": np.nan, "average_bil_exposure": np.nan, "average_risky_exposure": np.nan, "active_weeks": 0}
    wealth = (1.0 + r).cumprod()
    ann_ret = float(wealth.iloc[-1] ** (52.0 / len(r)) - 1.0) if wealth.iloc[-1] > 0 else np.nan
    ann_vol = float(r.std(ddof=0) * math.sqrt(52.0))
    mdd = max_drawdown(r)
    q5 = r.quantile(0.05)
    return {
        "annual_return": ann_ret,
        "annual_volatility": ann_vol,
        "sharpe": float(ann_ret / ann_vol) if ann_vol > 0 else np.nan,
        "max_drawdown": mdd,
        "calmar": float(ann_ret / abs(mdd)) if pd.notna(mdd) and mdd < 0 else np.nan,
        "cvar_5": float(r[r <= q5].mean()) if pd.notna(q5) else np.nan,
        "average_turnover": float(path.get("turnover", pd.Series(dtype=float)).reindex(r.index).mean()),
        "annual_cost_drag": float(path.get("cost", pd.Series(dtype=float)).reindex(r.index).mean() * 52.0),
        "average_bil_exposure": float(path.get("bil_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_risky_exposure": float(path.get("risky_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def load_inputs(mlx5: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-8 inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    mlx5.validate_inputs(features, targets)
    weekly_returns = mlx5.load_panel_csv(WEEKLY_RETURNS_IN)
    return features, targets, weekly_returns


def choose_universe(weekly_returns: pd.DataFrame, warnings_list: list[str]) -> list[str]:
    preferred = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "HYG", "LQD", "GLD", "SLV", "DBC", "USO", "VNQ", "XLK", "XLF", "XLE", "XLV", "SMH", "BIL"]
    available = [t for t in preferred if t in weekly_returns.columns]
    missing = [t for t in preferred if t not in weekly_returns.columns]
    if missing:
        warn(f"RL universe skipped unavailable preferred tickers: {missing}", warnings_list)
    if "BIL" not in available:
        raise ValueError("BIL is required for MLX-8 cash/safe asset but is missing from weekly returns.")
    return available


def safe_feature_columns(features: pd.DataFrame) -> list[str]:
    cols = []
    for col in features.columns:
        if col in {"Date", "ticker"}:
            continue
        lower = col.lower()
        if col in TARGET_COLUMNS or lower.startswith(TARGET_LIKE_PREFIXES) or lower.endswith("_label"):
            continue
        if pd.api.types.is_numeric_dtype(features[col]):
            cols.append(col)
    return cols


def build_observation_features(features: pd.DataFrame, weekly_returns: pd.DataFrame, universe: list[str], warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    all_dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    obs_parts: list[pd.DataFrame] = []
    ticker_feature_cols = [
        "trailing_return_1w",
        "trailing_return_4w",
        "trailing_return_13w",
        "trailing_return_26w",
        "realized_vol_13w",
        "realized_vol_26w",
        "momentum_12_1",
        "rolling_sharpe_13w",
        "drawdown_from_52w_high",
        "cross_sectional_return_rank_13w",
    ]
    for col in ticker_feature_cols:
        if col not in features.columns:
            continue
        pivot = features[features["ticker"].isin(universe)].pivot(index="Date", columns="ticker", values=col).reindex(index=all_dates, columns=universe)
        pivot.columns = [f"{ticker}_{col}" for ticker in pivot.columns]
        obs_parts.append(pivot)

    date_patterns = ("market_state_", "risk_", "regime", "transition", "breadth", "vix", "google", "stress", "drawdown", "trend", "corr", "macro", "confidence", "overlay", "target_vol", "p_")
    date_cols = []
    for col in safe_feature_columns(features):
        lower = col.lower()
        if col in ticker_feature_cols:
            continue
        if lower.startswith(date_patterns) or any(pattern in lower for pattern in date_patterns):
            date_cols.append(col)
    if date_cols:
        date_level = features[["Date"] + date_cols].drop_duplicates("Date").set_index("Date").reindex(all_dates)
        date_level.columns = [f"date_{c}" for c in date_level.columns]
        obs_parts.append(date_level)

    returns = weekly_returns.reindex(all_dates, columns=universe)
    for window in (4, 13, 26):
        obs_parts.append(((1.0 + returns).rolling(window, min_periods=max(2, window // 4)).apply(np.prod, raw=True) - 1.0).add_prefix(f"ret{window}_"))
        obs_parts.append((returns.rolling(window, min_periods=max(2, window // 4)).std() * math.sqrt(52.0)).add_prefix(f"vol{window}_"))

    for prefix, path in [("mlx5", SEQUENCE_PREDICTIONS_IN), ("mlx6", TRANSFORMER_PREDICTIONS_IN)]:
        if not path.exists():
            warn(f"Optional {prefix} prediction file missing for RL observation confidence features: {path}", warnings_list)
            continue
        try:
            pred = pd.read_parquet(path)
            pred["Date"] = pd.to_datetime(pred["Date"])
            rows = []
            for date, group in pred.groupby("Date"):
                score = pd.to_numeric(group["score"], errors="coerce").dropna()
                if score.empty:
                    continue
                rows.append({
                    "Date": date,
                    f"{prefix}_score_mean": float(score.mean()),
                    f"{prefix}_score_std": float(score.std(ddof=0)),
                    f"{prefix}_score_top10_mean": float(score.sort_values(ascending=False).head(10).mean()),
                    f"{prefix}_score_top1_minus_median": float(score.max() - score.median()),
                })
            conf = pd.DataFrame(rows).set_index("Date").reindex(all_dates) if rows else pd.DataFrame()
            if not conf.empty:
                obs_parts.append(conf)
        except Exception as exc:
            warn(f"Could not load {prefix} confidence features for RL observations: {exc}", warnings_list)

    obs = pd.concat(obs_parts, axis=1).sort_index()
    split = split_for_dates(obs.index)
    train_mask = split.eq("train")
    medians = obs.loc[train_mask].median(numeric_only=True).fillna(0.0)
    filled = obs.fillna(medians).fillna(0.0)
    means = filled.loc[train_mask].mean(numeric_only=True)
    stds = filled.loc[train_mask].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    scaled = ((filled - means) / stds).replace([np.inf, -np.inf], 0.0).fillna(0.0).astype("float32")
    meta = {
        "raw_observation_feature_count": int(obs.shape[1]),
        "scaled_observation_feature_count": int(scaled.shape[1]),
        "median_fill_values": medians.to_dict(),
        "standardization_means": means.to_dict(),
        "standardization_stds": stds.to_dict(),
    }
    return scaled, meta


def state_labels(mlx5: Any, features: pd.DataFrame) -> pd.Series:
    return mlx5.infer_market_state_by_date(features)


def split_dates(all_dates: pd.DatetimeIndex, split_name: str) -> pd.DatetimeIndex:
    if split_name == "train":
        start, end = pd.Timestamp("1900-01-01"), pd.Timestamp("2017-12-31")
    elif split_name == "validation":
        start, end = pd.Timestamp("2018-01-01"), pd.Timestamp("2019-12-31")
    elif split_name == "holdout":
        start, end = pd.Timestamp("2020-01-01"), pd.Timestamp("2100-01-01")
    else:
        raise ValueError(f"Unknown split {split_name}")
    next_dates = pd.Series(all_dates[1:].tolist() + [pd.NaT], index=all_dates)
    dates = all_dates[(all_dates >= start) & (all_dates <= end)]
    dates = pd.DatetimeIndex([d for d in dates if pd.notna(next_dates.loc[d]) and next_dates.loc[d] <= end])
    return dates


def softmax(action: np.ndarray) -> np.ndarray:
    x = np.asarray(action, dtype="float64")
    x = x - np.nanmax(x)
    ex = np.exp(np.clip(x, -30, 30))
    denom = ex.sum()
    if not np.isfinite(denom) or denom <= 0:
        return np.ones_like(ex) / len(ex)
    return ex / denom


def initial_weights(universe: list[str]) -> np.ndarray:
    w = np.zeros(len(universe), dtype="float32")
    if "BIL" in universe:
        w[universe.index("BIL")] = 1.0
    else:
        w[:] = 1.0 / len(universe)
    return w


class PortfolioAllocationEnv(GYM_ENV_BASE):
    metadata = {"render_modes": []}

    def __init__(self, gym: Any, obs_features: pd.DataFrame, next_returns: pd.DataFrame, dates: pd.DatetimeIndex, universe: list[str], state: pd.Series, reward_variant: str, cost_bps: float = DEFAULT_COST_BPS):
        self.gym = gym
        self.spaces = gym.spaces
        self.obs_features = obs_features.reindex(dates)
        self.next_returns = next_returns.reindex(index=dates, columns=universe).fillna(0.0)
        self.dates = pd.DatetimeIndex(dates)
        self.universe = universe
        self.state = state.reindex(dates).fillna("unknown")
        self.reward_variant = reward_variant
        self.cost_bps = cost_bps
        self.n_assets = len(universe)
        self.base_dim = int(self.obs_features.shape[1])
        self.observation_space = self.spaces.Box(low=-10.0, high=10.0, shape=(self.base_dim + self.n_assets,), dtype=np.float32)
        self.action_space = self.spaces.Box(low=-5.0, high=5.0, shape=(self.n_assets,), dtype=np.float32)
        self._safe_idx = [i for i, t in enumerate(universe) if t in SAFE_ASSETS]
        self._reset_state()

    def _reset_state(self) -> None:
        self.i = 0
        self.prev_weights = initial_weights(self.universe)
        self.equity = 1.0
        self.peak = 1.0
        self.recent_returns: list[float] = []

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        self._reset_state()
        return self._obs(), {}

    def _obs(self) -> np.ndarray:
        if len(self.dates) == 0:
            base = np.zeros(self.base_dim, dtype="float32")
        else:
            idx = min(self.i, len(self.dates) - 1)
            base = self.obs_features.iloc[idx].to_numpy(dtype="float32")
        obs = np.concatenate([base, self.prev_weights.astype("float32")])
        return np.clip(obs, -10, 10).astype("float32")

    def _risky_exposure(self, weights: np.ndarray) -> float:
        safe = float(weights[self._safe_idx].sum()) if self._safe_idx else 0.0
        return float(max(0.0, 1.0 - safe))

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        weights = softmax(action).astype("float32")
        date = self.dates[self.i]
        returns = self.next_returns.loc[date].to_numpy(dtype="float64")
        gross = float(np.dot(weights, np.nan_to_num(returns, nan=0.0)))
        turnover = float(np.abs(weights - self.prev_weights).sum())
        cost = turnover * (self.cost_bps / 10000.0)
        net = gross - cost
        self.equity *= 1.0 + net
        self.peak = max(self.peak, self.equity)
        drawdown = self.equity / self.peak - 1.0
        self.recent_returns.append(net)
        recent_vol = float(np.std(self.recent_returns[-13:], ddof=0)) if len(self.recent_returns) >= 4 else 0.0
        risky = self._risky_exposure(weights)
        state = str(self.state.loc[date])

        reward = net
        if self.reward_variant in {"turnover_penalized", "risk_aware", "defensive_regime_aware"}:
            reward -= 0.0010 * turnover
        if self.reward_variant in {"risk_aware", "defensive_regime_aware"}:
            reward -= 0.05 * recent_vol
            reward -= 0.02 * max(0.0, -drawdown)
        if self.reward_variant == "defensive_regime_aware":
            if state == "stressed_panic":
                reward -= 0.0020 * risky
            elif state in {"neutral_mixed", "recovery_fragile"}:
                reward -= 0.0005 * risky

        self.prev_weights = weights.copy()
        info = {
            "Date": date,
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": float(weights[self.universe.index("BIL")]) if "BIL" in self.universe else 0.0,
            "risky_exposure": risky,
            "drawdown": drawdown,
            "equity": self.equity,
            "market_state": state,
            "weights": weights.copy(),
            "raw_action": np.asarray(action, dtype="float32").copy(),
        }
        self.i += 1
        terminated = self.i >= len(self.dates)
        return self._obs(), float(reward), terminated, False, info


def build_next_returns(obs_features: pd.DataFrame, weekly_returns: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    returns = weekly_returns.reindex(obs_features.index, columns=universe)
    return returns.shift(-1)


def make_env(gym: Any, obs_features: pd.DataFrame, next_returns: pd.DataFrame, all_dates: pd.DatetimeIndex, split_name: str, universe: list[str], state: pd.Series, reward_variant: str) -> PortfolioAllocationEnv:
    dates = split_dates(all_dates, split_name)
    return PortfolioAllocationEnv(gym, obs_features, next_returns, dates, universe, state, reward_variant)


def evaluate_policy(model: Any, env: PortfolioAllocationEnv, run: RLRun, split_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    obs, _ = env.reset(seed=run.seed)
    rows: list[dict[str, Any]] = []
    weights_rows: list[dict[str, Any]] = []
    pred_rows: list[dict[str, Any]] = []
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = bool(terminated or truncated)
        date = pd.Timestamp(info["Date"])
        weights = info["weights"]
        raw_action = info["raw_action"]
        rows.append({
            "Date": date,
            "strategy_name": run.strategy_name,
            "algorithm": run.algorithm,
            "reward_variant": run.reward_variant,
            "seed": run.seed,
            "split": split_name,
            "gross_return": info["gross_return"],
            "net_return": info["net_return"],
            "turnover": info["turnover"],
            "cost": info["cost"],
            "bil_weight": info["bil_weight"],
            "risky_exposure": info["risky_exposure"],
            "drawdown": info["drawdown"],
            "equity": info["equity"],
            "market_state": info["market_state"],
            "reward": reward,
            "total_timesteps": run.total_timesteps,
        })
        pred_rows.append({
            "Date": date,
            "strategy_name": run.strategy_name,
            "algorithm": run.algorithm,
            "reward_variant": run.reward_variant,
            "seed": run.seed,
            "split": split_name,
            "max_weight": float(weights.max()),
            "bil_weight": info["bil_weight"],
            "risky_exposure": info["risky_exposure"],
            "raw_action_l2": float(np.sqrt(np.square(raw_action).sum())),
            "top_ticker": env.universe[int(np.argmax(weights))],
        })
        for ticker, weight, raw in zip(env.universe, weights, raw_action):
            weights_rows.append({
                "Date": date,
                "strategy_name": run.strategy_name,
                "algorithm": run.algorithm,
                "reward_variant": run.reward_variant,
                "seed": run.seed,
                "split": split_name,
                "ticker": ticker,
                "weight": float(weight),
                "raw_action": float(raw),
            })
    return pd.DataFrame(rows), pd.DataFrame(weights_rows), pd.DataFrame(pred_rows)


def select_project_strategy_files(mlx5: Any, warnings_list: list[str]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    fixed = {
        "production": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
        "official_shadow": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_combo_abc.csv",
    }
    for name, path in fixed.items():
        if path.exists():
            selected[name] = path
        else:
            warn(f"Project strategy file missing for {name}: {path}", warnings_list)
    if SEQUENCE_PROJECT_COMPARISON_IN.exists():
        comp = pd.read_csv(SEQUENCE_PROJECT_COMPARISON_IN)
        for category, alias in [("phase4b", "phase4b"), ("phase6", "phase6"), ("phase7", "phase7")]:
            sub = comp[comp["category"].eq(category)] if "category" in comp.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No project strategy comparison found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
            path = ROOT / str(row["source_path"])
            if path.exists():
                selected[alias] = path
            else:
                warn(f"Selected project file missing for {category}: {path}", warnings_list)
    return selected


def read_project_return_file(mlx5: Any, path: Path, warnings_list: list[str]) -> pd.DataFrame:
    try:
        return mlx5.read_project_return_file(path)
    except Exception as exc:
        warn(f"Could not read project return file {path}: {exc}", warnings_list)
        return pd.DataFrame()


def benchmark_returns(mlx5: Any, weekly_returns: pd.DataFrame, warnings_list: list[str]) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for name, path in select_project_strategy_files(mlx5, warnings_list).items():
        frame = read_project_return_file(mlx5, path, warnings_list)
        if not frame.empty:
            out[name] = frame["net_return"].rename(name)
    if "SPY" in weekly_returns.columns:
        out["SPY"] = weekly_returns["SPY"].rename("SPY")
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond:
        out["60_40"] = (0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]).rename("60_40")
    if SEQUENCE_BACKTEST_IN.exists() and SEQUENCE_SUMMARY_IN.exists():
        seq_summary = pd.read_csv(SEQUENCE_SUMMARY_IN)
        mom = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("baseline_momentum"))]
        seq = pd.read_csv(SEQUENCE_BACKTEST_IN, parse_dates=["Date"])
        if not mom.empty:
            best_name = mom.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            frame = seq[seq["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not frame.empty:
                out["simple_momentum"] = frame["net_return"].rename("simple_momentum")
        model = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("model")) & (~seq_summary["wrapper"].eq("raw_ml"))]
        if not model.empty:
            best_name = model.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            frame = seq[seq["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not frame.empty:
                out["mlx5_sequence"] = frame["net_return"].rename("mlx5_sequence")
    if TRANSFORMER_BACKTEST_IN.exists() and TRANSFORMER_SUMMARY_IN.exists():
        tr_summary = pd.read_csv(TRANSFORMER_SUMMARY_IN)
        tr = pd.read_csv(TRANSFORMER_BACKTEST_IN, parse_dates=["Date"])
        sub = tr_summary[(tr_summary["split"].eq("holdout")) & (~tr_summary["wrapper"].eq("raw_ml"))]
        if not sub.empty:
            best_name = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            frame = tr[tr["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not frame.empty:
                out["mlx6_transformer"] = frame["net_return"].rename("mlx6_transformer")
    if META_RETURNS_IN.exists() and META_SUMMARY_IN.exists():
        meta_summary = pd.read_csv(META_SUMMARY_IN)
        meta = pd.read_csv(META_RETURNS_IN, parse_dates=["Date"])
        sub = meta_summary[(meta_summary["split"].eq("holdout")) & (~meta_summary["strategy_family"].isin(["benchmark", "benchmark_summary_only"]))]
        if not sub.empty:
            best_name = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            frame = meta[meta["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not frame.empty:
                out["mlx7_meta_label"] = frame["net_return"].rename("mlx7_meta_label")
    return out


def comparison_table(rl_summary: pd.DataFrame, weekly_returns: pd.DataFrame, mlx5: Any, warnings_list: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hold = rl_summary[rl_summary["split"].eq("holdout")].copy()
    for _, row in hold.iterrows():
        d = row.to_dict()
        d["comparison_label"] = d["strategy_name"]
        d["category"] = "rl_policy"
        rows.append(d)
    bench = benchmark_returns(mlx5, weekly_returns, warnings_list)
    for name, series in bench.items():
        path = pd.DataFrame({"net_return": series, "gross_return": series, "turnover": np.nan, "cost": 0.0, "bil_weight": 0.0, "risky_exposure": np.nan})
        path["split"] = split_for_dates(path.index).values
        metrics = calc_metrics(path[path["split"].eq("holdout")])
        metrics.update({"strategy_name": name, "comparison_label": name, "category": "benchmark", "split": "holdout"})
        rows.append(metrics)
    if MLX5C_SUMMARY_IN.exists():
        try:
            mlx5c = json.loads(MLX5C_SUMMARY_IN.read_text())
            rows.append({
                "annual_return": np.nan,
                "annual_volatility": np.nan,
                "sharpe": mlx5c.get("overall_mean_sharpe", np.nan),
                "max_drawdown": mlx5c.get("overall_worst_case_max_drawdown", np.nan),
                "calmar": np.nan,
                "cvar_5": mlx5c.get("overall_worst_case_cvar_5", np.nan),
                "average_turnover": np.nan,
                "annual_cost_drag": np.nan,
                "average_bil_exposure": np.nan,
                "average_risky_exposure": np.nan,
                "active_weeks": np.nan,
                "strategy_name": "mlx5c_bil_fallback_mean_summary",
                "comparison_label": "mlx5c_bil_fallback_mean_summary",
                "category": "benchmark_summary_only",
                "split": "holdout",
            })
        except Exception as exc:
            warn(f"Could not load MLX-5C summary comparison: {exc}", warnings_list)
    return pd.DataFrame(rows)


def state_by_state(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hold = returns[returns["split"].eq("holdout")].copy()
    for (strategy, state), group in hold.groupby(["strategy_name", "market_state"], dropna=False):
        metrics = calc_metrics(group.set_index("Date"))
        metrics.update({"strategy_name": strategy, "market_state": state, "weeks": int(len(group))})
        rows.append(metrics)
    return pd.DataFrame(rows)


def exposure_audit(weights: pd.DataFrame, universe_meta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if weights.empty:
        return pd.DataFrame()
    category = {}
    if not universe_meta.empty and {"ticker", "category"}.issubset(universe_meta.columns):
        category = universe_meta.drop_duplicates("ticker").set_index("ticker")["category"].to_dict()
    hold = weights[weights["split"].eq("holdout")].copy()
    for strategy, group in hold.groupby("strategy_name"):
        pivot = group.pivot_table(index="Date", columns="ticker", values="weight", aggfunc="mean").fillna(0.0)
        avg = pivot.mean().sort_values(ascending=False)
        for ticker, value in avg.items():
            rows.append({
                "strategy_name": strategy,
                "audit_type": "ticker",
                "item": ticker,
                "category": category.get(ticker, "unknown"),
                "average_weight": float(value),
                "max_weight": float(pivot[ticker].max()),
                "holding_frequency": float((pivot[ticker] > 0.01).mean()),
            })
        for cat in sorted(set(category.get(t, "unknown") for t in pivot.columns)):
            cols = [t for t in pivot.columns if category.get(t, "unknown") == cat]
            series = pivot[cols].sum(axis=1)
            rows.append({
                "strategy_name": strategy,
                "audit_type": "category",
                "item": cat,
                "category": cat,
                "average_weight": float(series.mean()),
                "max_weight": float(series.max()),
                "holding_frequency": float((series > 0.01).mean()),
            })
        for label, cols in {
            "average_SPY_QQQ_SMH_weight": [c for c in ["SPY", "QQQ", "SMH"] if c in pivot.columns],
            "average_BIL_weight": [c for c in ["BIL"] if c in pivot.columns],
            "average_safe_asset_weight": [c for c in pivot.columns if c in SAFE_ASSETS],
            "average_top3_weight": [],
        }.items():
            if label == "average_top3_weight":
                value = pivot.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1).mean()
                max_value = pivot.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1).max()
            elif cols:
                value = pivot[cols].sum(axis=1).mean()
                max_value = pivot[cols].sum(axis=1).max()
            else:
                value = np.nan
                max_value = np.nan
            rows.append({"strategy_name": strategy, "audit_type": "summary", "item": label, "category": "", "average_weight": float(value) if pd.notna(value) else np.nan, "max_weight": float(max_value) if pd.notna(max_value) else np.nan, "holding_frequency": np.nan})
    return pd.DataFrame(rows)


def best_row(df: pd.DataFrame, split: str = "holdout", metric: str = "sharpe", ascending: bool = False) -> dict[str, Any] | None:
    sub = df[df["split"].eq(split)].copy() if "split" in df.columns else df.copy()
    sub = sub[pd.to_numeric(sub[metric], errors="coerce").notna()]
    if sub.empty:
        return None
    return sub.sort_values([metric, "annual_return"], ascending=[ascending, False]).iloc[0].to_dict()


def pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}"


def num(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "No rows available."
    sub = df[[c for c in cols if c in df.columns]].head(max_rows).copy()
    pct_cols = [c for c in sub.columns if c in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "annual_cost_drag", "average_bil_exposure", "average_risky_exposure", "average_turnover", "average_weight", "max_weight", "holding_frequency"}]
    for col in pct_cols:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(pct)
    for col in [c for c in ["sharpe", "calmar"] if c in sub.columns]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(num)
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def choose_recommendation(selected: dict[str, Any] | None, comparison: pd.DataFrame) -> str:
    if not selected:
        return "REJECT"
    rl_sharpe = float(selected.get("sharpe", np.nan))
    prod = comparison[comparison["strategy_name"].eq("production")]
    phase4b = comparison[comparison["strategy_name"].eq("phase4b")]
    mlx5c = comparison[comparison["strategy_name"].eq("mlx5c_bil_fallback_mean_summary")]
    prod_sharpe = float(prod.iloc[0]["sharpe"]) if not prod.empty and pd.notna(prod.iloc[0]["sharpe"]) else np.nan
    phase4b_sharpe = float(phase4b.iloc[0]["sharpe"]) if not phase4b.empty and pd.notna(phase4b.iloc[0]["sharpe"]) else np.nan
    mlx5c_sharpe = float(mlx5c.iloc[0]["sharpe"]) if not mlx5c.empty and pd.notna(mlx5c.iloc[0]["sharpe"]) else np.nan
    if pd.notna(mlx5c_sharpe) and rl_sharpe > mlx5c_sharpe and pd.notna(phase4b_sharpe) and rl_sharpe > phase4b_sharpe:
        return "PROCEED TO ENSEMBLE TESTING"
    if pd.notna(prod_sharpe) and rl_sharpe > prod_sharpe:
        return "PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION"
    if rl_sharpe > 0.4:
        return "NEEDS MORE TRAINING / BETTER ENVIRONMENT"
    return "KEEP AS RESEARCH ONLY"


def reward_definitions() -> dict[str, Any]:
    return {
        "transaction_cost_bps": DEFAULT_COST_BPS,
        "return_only": "reward = weekly net return after transaction cost",
        "turnover_penalized": "reward = weekly net return - 0.0010 * turnover",
        "risk_aware": "reward = weekly net return - 0.0010 * turnover - 0.05 * trailing weekly volatility - 0.02 * drawdown depth",
        "defensive_regime_aware": "risk_aware plus extra risky-exposure penalty in stressed_panic and smaller penalty in neutral_mixed/recovery_fragile",
    }


def write_notes(package_meta: dict[str, Any], universe: list[str], training_log: pd.DataFrame, summary: pd.DataFrame, comparison: pd.DataFrame, state: pd.DataFrame, exposure: pd.DataFrame, skipped: list[dict[str, Any]], summary_json: dict[str, Any], warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    best_val = summary_json.get("best_validation_policy", {})
    best_hold = summary_json.get("best_holdout_policy", {})
    selected = summary_json.get("selected_validation_policy_holdout", {})
    skip_lines = "\n".join(f"- {s.get('algorithm') or s.get('run')}: {s.get('reason')}" for s in skipped) or "- None"
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"
    holdout = summary[summary["split"].eq("holdout")].sort_values(["sharpe", "annual_return"], ascending=[False, False]) if not summary.empty else pd.DataFrame()
    comp = comparison.sort_values(["sharpe", "annual_return"], ascending=[False, False]) if not comparison.empty else pd.DataFrame()
    exp = exposure[exposure["strategy_name"].eq(best_hold.get("strategy_name", ""))].sort_values("average_weight", ascending=False) if not exposure.empty else pd.DataFrame()
    st = state[state["strategy_name"].eq(best_hold.get("strategy_name", ""))].sort_values("sharpe", ascending=False) if not state.empty and "sharpe" in state.columns else pd.DataFrame()

    NOTES_OUT.write_text(f"""# Phase MLX Reinforcement Learning Notes

## Research-Only Warning

Phase MLX-8 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Reinforcement learning is a setup where an agent learns by taking actions in an environment and receiving rewards. The environment is the simulated weekly ETF market. The observation is the information the agent sees at date `t`, such as recent ETF returns, volatility, regime features, model confidence summaries, and previous portfolio weights. The action is a long-only ETF allocation. The reward function is the score the agent tries to maximize, such as return after turnover costs, volatility penalties, drawdown penalties, and defensive regime penalties.

PPO is a policy-gradient RL algorithm that updates a policy cautiously so each new policy does not move too far from the previous one. SAC and A2C are other RL algorithms, but they were skipped here to keep the overnight CPU run bounded. RL is different from supervised learning because it learns a sequence of decisions and their consequences rather than labels for independent examples.

RL might help portfolio allocation because it can directly optimize allocation behavior with turnover, drawdown, and cash decisions in the loop. It is extremely overfit-prone in finance because the historical environment is short, noisy, non-stationary, and easy to memorize. Here, RL is used only to test whether an agent can learn useful long-only ETF weights across a small research universe.

## Technical Setup

- Packages: gymnasium={package_meta.get('gymnasium')}, stable_baselines3={package_meta.get('stable_baselines3')}, torch={package_meta.get('torch')}
- RL universe: {universe}
- Observation features: selected ETF trailing returns, momentum, realized volatility, drawdown, rank features, date-level regime/risk/breadth/fear features, MLX-5/6 confidence summaries, and previous portfolio weights.
- Action space: continuous Box action converted with softmax into long-only weights summing to 1.
- Reward functions: `{', '.join(REWARD_VARIANTS)}`
- Algorithm used: PPO
- Algorithms skipped: SAC and A2C for bounded CPU runtime.
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Transaction cost: 10 bps per unit turnover.
- Leakage controls: observations at date `t` use known-at-date features only; action at `t` earns next-week return; target/forward columns are excluded.

## Results

- Runs completed: {summary_json.get('runs_completed')}
- Runs skipped: {len(skipped)}
- Best validation policy: `{best_val.get('strategy_name', 'n/a')}` with validation Sharpe {num(best_val.get('sharpe', np.nan))}
- Selected policy holdout Sharpe: {num(selected.get('sharpe', np.nan))}
- Best holdout policy: `{best_hold.get('strategy_name', 'n/a')}` with holdout Sharpe {num(best_hold.get('sharpe', np.nan))}

{markdown_table(holdout, ['strategy_name', 'reward_variant', 'seed', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_exposure', 'average_risky_exposure'], max_rows=20)}

## Benchmark Comparison

{markdown_table(comp, ['comparison_label', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_exposure', 'average_risky_exposure'], max_rows=28)}

## State-By-State Results

{markdown_table(st, ['market_state', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_risky_exposure', 'weeks'], max_rows=20)}

## Exposure Audit

{markdown_table(exp, ['audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], max_rows=30)}

## Interpretation

- Did RL beat production? {summary_json.get('selected_beats_production_sharpe')}
- Did RL beat Phase 4B? {summary_json.get('selected_beats_phase4b_sharpe')}
- Did RL beat MLX-5C? {summary_json.get('selected_beats_mlx5c_sharpe')}
- Did risk-aware reward reduce drawdown? {summary_json.get('risk_aware_helped_drawdown')}
- Final recommendation: **{summary_json.get('final_recommendation')}**

RL should remain research-only unless it survives richer walk-forward testing and a cleaner environment. A high holdout Sharpe alone is not enough because RL can learn brittle historical exposure patterns.

## Skipped Runs

{skip_lines}

## Warnings

{warn_lines}
""")


def empty_outputs(reason: str, package_meta: dict[str, Any], warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in [TRAINING_LOG_OUT, BACKTEST_RETURNS_OUT, SUMMARY_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, EXPOSURE_AUDIT_OUT]:
        pd.DataFrame().to_csv(path, index=False)
    for path in [POLICY_PREDICTIONS_OUT, POLICY_WEIGHTS_OUT]:
        pd.DataFrame().to_parquet(path, index=False)
    REWARD_DEFINITIONS_OUT.write_text(json.dumps(reward_definitions(), indent=2, default=json_default))
    skipped = [{"run": "all_rl", "reason": reason}]
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))
    summary = {"phase": "MLX-8 reinforcement learning", "research_only": True, "production_valid": False, "package_status": package_meta, "reason": reason, "warnings": warnings_list}
    SUMMARY_JSON_OUT.write_text(json.dumps(summary, indent=2, default=json_default))
    NOTES_OUT.write_text(f"""# Phase MLX Reinforcement Learning Notes

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

Reinforcement learning trains an agent to act in an environment. MLX-8 was skipped because {reason}.
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    package_meta = package_status()
    if not package_meta["gymnasium"]["available"] or not package_meta["stable_baselines3"]["available"]:
        reason = "gymnasium or stable_baselines3 missing"
        warn(reason, warnings_list)
        empty_outputs(reason, package_meta, warnings_list)
        return

    import gymnasium as gym
    from stable_baselines3 import PPO

    mlx5 = load_mlx5_module()
    features, targets, weekly_returns = load_inputs(mlx5)
    universe = choose_universe(weekly_returns, warnings_list)
    universe_meta = pd.read_csv(UNIVERSE_IN) if UNIVERSE_IN.exists() else pd.DataFrame()
    obs_features, obs_meta = build_observation_features(features, weekly_returns, universe, warnings_list)
    next_returns = build_next_returns(obs_features, weekly_returns, universe)
    states = state_labels(mlx5, features)
    all_dates = pd.DatetimeIndex(obs_features.index)

    runs = [RLRun("PPO", reward, seed, TOTAL_TIMESTEPS) for reward in REWARD_VARIANTS for seed in SEEDS]
    skipped = [
        {"algorithm": "SAC", "reason": "skipped to keep bounded overnight CPU run focused on PPO"},
        {"algorithm": "A2C", "reason": "skipped to keep bounded overnight CPU run focused on PPO"},
    ]

    training_rows: list[dict[str, Any]] = []
    returns_frames: list[pd.DataFrame] = []
    weights_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for idx, run in enumerate(runs, start=1):
        print(f"Running MLX-8 RL {idx}/{len(runs)}: {run.strategy_name} timesteps={run.total_timesteps}", flush=True)
        random.seed(run.seed)
        np.random.seed(run.seed)
        train_env = make_env(gym, obs_features, next_returns, all_dates, "train", universe, states, run.reward_variant)
        start = time.time()
        model = PPO(
            "MlpPolicy",
            train_env,
            seed=run.seed,
            verbose=0,
            learning_rate=3e-4,
            n_steps=256,
            batch_size=128,
            n_epochs=5,
            gamma=0.99,
            gae_lambda=0.95,
            ent_coef=0.001,
            policy_kwargs={"net_arch": [64, 64]},
        )
        model.learn(total_timesteps=run.total_timesteps, progress_bar=False)
        train_seconds = time.time() - start
        training_rows.append({"strategy_name": run.strategy_name, "algorithm": run.algorithm, "reward_variant": run.reward_variant, "seed": run.seed, "total_timesteps": run.total_timesteps, "train_seconds": train_seconds, "status": "completed"})

        for split_name in ("train", "validation", "holdout"):
            env = make_env(gym, obs_features, next_returns, all_dates, split_name, universe, states, run.reward_variant)
            ret, weights, preds = evaluate_policy(model, env, run, split_name)
            returns_frames.append(ret)
            weights_frames.append(weights)
            prediction_frames.append(preds)
            metrics = calc_metrics(ret.set_index("Date"))
            metrics.update({"strategy_name": run.strategy_name, "algorithm": run.algorithm, "reward_variant": run.reward_variant, "seed": run.seed, "split": split_name, "total_timesteps": run.total_timesteps})
            summary_rows.append(metrics)

    training_log = pd.DataFrame(training_rows)
    returns_df = pd.concat(returns_frames, ignore_index=True) if returns_frames else pd.DataFrame()
    weights_df = pd.concat(weights_frames, ignore_index=True) if weights_frames else pd.DataFrame()
    predictions_df = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    comparison = comparison_table(summary, weekly_returns, mlx5, warnings_list)
    state = state_by_state(returns_df)
    exposure = exposure_audit(weights_df, universe_meta)

    best_val = best_row(summary, "validation")
    selected_holdout = None
    if best_val:
        selected_name = best_val["strategy_name"]
        selected_rows = summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq(selected_name))]
        selected_holdout = selected_rows.iloc[0].to_dict() if not selected_rows.empty else None
    best_holdout = best_row(summary, "holdout")

    def comp_value(name: str, metric: str) -> float:
        sub = comparison[comparison["strategy_name"].eq(name)] if not comparison.empty else pd.DataFrame()
        return float(sub.iloc[0][metric]) if not sub.empty and pd.notna(sub.iloc[0][metric]) else np.nan

    selected_sharpe = float(selected_holdout.get("sharpe", np.nan)) if selected_holdout else np.nan
    selected_dd = float(selected_holdout.get("max_drawdown", np.nan)) if selected_holdout else np.nan
    prod_sharpe = comp_value("production", "sharpe")
    phase4b_sharpe = comp_value("phase4b", "sharpe")
    mlx5c_sharpe = comp_value("mlx5c_bil_fallback_mean_summary", "sharpe")
    risk_rows = summary[(summary["split"].eq("holdout")) & (summary["reward_variant"].isin(["risk_aware", "defensive_regime_aware"]))]
    return_rows = summary[(summary["split"].eq("holdout")) & (summary["reward_variant"].eq("return_only"))]
    risk_aware_helped_drawdown = bool(not risk_rows.empty and not return_rows.empty and risk_rows["max_drawdown"].max() > return_rows["max_drawdown"].max())
    recommendation = choose_recommendation(selected_holdout, comparison)

    TRAINING_LOG_OUT.write_text(training_log.to_csv(index=False))
    predictions_df.to_parquet(POLICY_PREDICTIONS_OUT, index=False)
    weights_df.to_parquet(POLICY_WEIGHTS_OUT, index=False)
    returns_df.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    state.to_csv(STATE_BY_STATE_OUT, index=False)
    exposure.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    REWARD_DEFINITIONS_OUT.write_text(json.dumps(reward_definitions(), indent=2, default=json_default))
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))

    summary_json = {
        "phase": "MLX-8 reinforcement learning allocator",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "package_status": package_meta,
        "algorithms_run": ["PPO"],
        "algorithms_skipped": skipped,
        "reward_variants_run": list(REWARD_VARIANTS),
        "seeds_run": list(SEEDS),
        "total_timesteps_per_run": TOTAL_TIMESTEPS,
        "runs_completed": int(len(training_log)),
        "rl_universe": universe,
        "observation_metadata": obs_meta,
        "best_validation_policy": best_val or {},
        "selected_validation_policy_holdout": selected_holdout or {},
        "best_holdout_policy": best_holdout or {},
        "selected_beats_production_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(prod_sharpe) and selected_sharpe > prod_sharpe),
        "selected_beats_phase4b_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(phase4b_sharpe) and selected_sharpe > phase4b_sharpe),
        "selected_beats_mlx5c_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(mlx5c_sharpe) and selected_sharpe > mlx5c_sharpe),
        "selected_holdout_max_drawdown": selected_dd,
        "risk_aware_helped_drawdown": risk_aware_helped_drawdown,
        "final_recommendation": recommendation,
        "warnings": warnings_list + ["Experimental research-only Phase MLX output; not production-valid.", "No RL model is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "training_log": str(TRAINING_LOG_OUT.relative_to(ROOT)),
            "policy_predictions": str(POLICY_PREDICTIONS_OUT.relative_to(ROOT)),
            "policy_weights": str(POLICY_WEIGHTS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "state_by_state": str(STATE_BY_STATE_OUT.relative_to(ROOT)),
            "exposure_audit": str(EXPOSURE_AUDIT_OUT.relative_to(ROOT)),
            "reward_definitions": str(REWARD_DEFINITIONS_OUT.relative_to(ROOT)),
            "skipped_runs": str(SKIPPED_RUNS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(package_meta, universe, training_log, summary, comparison, state, exposure, skipped, summary_json, summary_json["warnings"])

    print("Phase MLX-8 reinforcement learning allocator")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Packages: {package_meta}")
    print("Algorithms run: PPO")
    print(f"Reward variants run: {list(REWARD_VARIANTS)}")
    print(f"Seeds run: {list(SEEDS)}")
    print(f"Total timesteps per run: {TOTAL_TIMESTEPS}")
    print(f"RL universe used: {universe}")
    print(f"Best validation policy: {best_val.get('strategy_name') if best_val else 'n/a'}")
    print(f"Best holdout policy: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Selected policy holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Final recommendation: {recommendation}")
    print("Outputs:")
    for path in [TRAINING_LOG_OUT, POLICY_PREDICTIONS_OUT, POLICY_WEIGHTS_OUT, BACKTEST_RETURNS_OUT, SUMMARY_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, EXPOSURE_AUDIT_OUT, REWARD_DEFINITIONS_OUT, SKIPPED_RUNS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
