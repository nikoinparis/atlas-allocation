"""Phase QQQ -- deep feature interaction mining.

Diagnostic-only research phase. Uses the PPP lagged ETF-characteristic panel,
OOO signal lineage, Layer 1 features, PPP factor context, and regime context to
mine stable nonlinear feature interactions under causal expanding-window
validation. No portfolio candidates, production pins, shadow pins, live trading,
or GGG1 logic are changed.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.special import expit
try:
    from scipy.stats import ConstantInputWarning
except Exception:  # pragma: no cover - older scipy fallback
    ConstantInputWarning = Warning
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, _tree


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in divide")
warnings.filterwarnings("ignore", category=ConstantInputWarning)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PPP = DATA / "research" / "phase_ppp_latent_factor_discovery"
OOO = DATA / "research" / "phase_ooo_signal_discovery"
L2A = DATA / "03_layer2a_strategy_logic"
L2B = DATA / "04_layer2b_risk_regime_engine"
L3 = DATA / "05_layer3_portfolio_construction"
OUT = DATA / "research" / "phase_qqq_deep_feature_interaction_mining"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"

INITIAL_TRAIN_DATES = 260
REFIT_FREQ = 26
TOP_Q = 0.75
RANDOM_STATE = 20260427
MAX_BASE_FEATURES = 115
MAX_MODEL_FEATURES_BASE = 95
MAX_MODEL_FEATURES_WITH_INTERACTIONS = 145
MAX_IMPORTANCE_ROWS_PER_FOLD = 70

TARGETS = [
    "target_etf_forward_top_quantile_4w",
    "target_etf_forward_top_quantile_8w",
    "target_etf_forward_risk_adjusted_top_quantile_4w",
    "target_etf_forward_risk_adjusted_top_quantile_8w",
]

TARGET_META = {
    "target_etf_forward_top_quantile_4w": {"horizon": 4, "return_col": "fwd_return_4w", "target_type": "forward_top_quantile"},
    "target_etf_forward_top_quantile_8w": {"horizon": 8, "return_col": "fwd_return_8w", "target_type": "forward_top_quantile"},
    "target_etf_forward_risk_adjusted_top_quantile_4w": {"horizon": 4, "return_col": "fwd_return_4w", "target_type": "risk_adjusted_top_quantile"},
    "target_etf_forward_risk_adjusted_top_quantile_8w": {"horizon": 8, "return_col": "fwd_return_8w", "target_type": "risk_adjusted_top_quantile"},
}

COMMANDS = [
    "sed -n '1,280p' docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md",
    "find data/research/phase_ppp_latent_factor_discovery -maxdepth 1 -type f | sort | xargs -I{} sh -c 'printf \"%s\\t\" \"$(basename \"{}\")\"; wc -l < \"{}\"'",
    "python3 - <<'PY' ...PPP schema and target/input summaries...",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md",
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md",
    "find data/research/phase_ooo_signal_discovery data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction -maxdepth 2 -type f | sort | sed -n '1,280p'",
    "ls -lh data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2b_combo_abc.csv",
    "python3 - <<'PY' ...available sklearn package check...",
    "tail -n 90 docs/research/project_journey.md",
    "python3 -m py_compile scripts/phase_qqq_deep_feature_interaction_mining.py",
    "python3 scripts/phase_qqq_deep_feature_interaction_mining.py",
]


@dataclass
class InteractionSpec:
    feature_name: str
    left: str
    right: str
    formula: str
    economic_interpretation: str
    event_func: Callable[[pd.DataFrame], pd.Series]
    family: str


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = next((c for c in ["date", "Date", "Unnamed: 0"] if c in df.columns), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df.index.name = "date"
    return df


def save_csv(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)


def clean_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", str(name)).strip("_")


def markdown_table(df: pd.DataFrame, n: int = 12, float_fmt: str = ".4f") -> str:
    if df is None or df.empty:
        return "_None._"
    view = df.head(n).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else format(float(x), float_fmt))
    view = view.astype(str).replace({"nan": "", "NaT": "", "None": ""})
    cols = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in view.iterrows():
        vals = [str(row[c]).replace("|", "\\|").replace("\n", " ") for c in view.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def forward_compound_returns(returns: pd.DataFrame, horizon: int) -> pd.DataFrame:
    r = returns.apply(pd.to_numeric, errors="coerce")
    future = r.shift(-1)
    log_future = np.log1p(future)
    fwd_log = log_future.rolling(horizon, min_periods=horizon).sum().shift(-(horizon - 1))
    valid_count = future.notna().rolling(horizon, min_periods=horizon).sum().shift(-(horizon - 1))
    out = np.expm1(fwd_log)
    return out.where(valid_count == horizon)


def add_top_quantile_target(df: pd.DataFrame, value_col: str, target_col: str) -> pd.Series:
    values = pd.to_numeric(df[value_col], errors="coerce")
    q = values.groupby(df["date"]).transform(lambda x: x.quantile(TOP_Q) if x.notna().sum() >= 8 else np.nan)
    return ((values >= q) & values.notna() & q.notna()).astype(float).where(values.notna() & q.notna())


def classify_family(feature: str) -> str:
    name = feature.lower()
    if feature.startswith("int_"):
        return "explicit_interaction"
    if name.startswith("state_lag1_") or "state_" in name or "market_state" in name or "risk_state" in name:
        return "regime_state_context"
    if "mom" in name or "xsmom" in name or "tsmom" in name:
        return "momentum"
    if "vol" in name or "quality" in name or "cvar" in name:
        return "volatility_quality"
    if "drawdown" in name or "stress" in name:
        return "drawdown_stress"
    if "trend" in name or "ma_distance" in name or "breadth" in name:
        return "trend_breadth"
    if "rel_strength" in name or "leadlag" in name:
        return "relative_strength_leadlag"
    if "carry" in name or "bab" in name or "value" in name or "reversal" in name:
        return "style_layer1"
    if name.startswith("ppp_factor"):
        return "ppp_latent_factor_context"
    if name.startswith("proxy_"):
        return "known_proxy_context"
    if name.startswith("ooo"):
        return "ooo_signal_lineage"
    if name.startswith("regime_"):
        return "regime_numeric_context"
    if name.startswith("z_"):
        return classify_family(name[2:])
    return "other"


def winsorize_series(s: pd.Series, low: float = 0.01, high: float = 0.99) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    lo = x.quantile(low)
    hi = x.quantile(high)
    if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
        return x
    return x.clip(lo, hi)


def cross_sectional_z(df: pd.DataFrame, col: str) -> pd.Series:
    x = pd.to_numeric(df[col], errors="coerce")
    mu = x.groupby(df["date"]).transform("mean")
    sd = x.groupby(df["date"]).transform("std").replace(0.0, np.nan)
    return ((x - mu) / sd).clip(-4.0, 4.0)


def load_ppp_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    returns = read_indexed(PPP / "ppp_panel_etf_returns.csv")
    characteristics = pd.read_csv(PPP / "ppp_panel_characteristics.csv")
    characteristics["date"] = pd.to_datetime(characteristics["date"], errors="coerce")
    manifest = pd.read_csv(PPP / "ppp_feature_manifest.csv")
    return returns, characteristics.dropna(subset=["date"]), manifest


def build_state_dummies(df: pd.DataFrame) -> list[str]:
    created = []
    for col, prefix in [("market_state_lag1", "state_lag1"), ("risk_state_lag1", "risk_lag1")]:
        if col not in df.columns:
            continue
        values = df[col].fillna("unknown").astype(str)
        for val in sorted(v for v in values.unique() if v and v != "nan"):
            name = f"{prefix}_{clean_name(val)}"
            df[name] = (values == val).astype(float)
            created.append(name)
    return created


def add_market_context(df: pd.DataFrame, returns: pd.DataFrame) -> tuple[list[str], list[dict]]:
    rows = []
    created = []
    proxy_cols = [c for c in ["SPY", "BIL", "TLT", "GLD", "HYG", "LQD", "QQQ", "EFA", "VWO", "DBA", "PDBC", "XLE"] if c in returns.columns]
    proxy = returns[proxy_cols].shift(1).reset_index(names="date")
    proxy = proxy.rename(columns={c: f"proxy_{c}_ret_lag1" for c in proxy_cols})
    df2 = df.merge(proxy, on="date", how="left", sort=False)
    for c in proxy_cols:
        col = f"proxy_{c}_ret_lag1"
        df[col] = df2[col].to_numpy()
        created.append(col)
        rows.append(
            {
                "feature_name": col,
                "source": "ppp_panel_etf_returns.csv",
                "feature_family": "known_proxy_context",
                "feature_type": "lagged_market_context",
                "lag_rule": "proxy ETF return shifted one week",
                "used_in_models": True,
                "leakage_check": "lagged proxy context only",
                "economic_interpretation": f"lagged {c} proxy return context",
            }
        )

    for path, prefix in [(PPP / "ppp_pca_factor_returns.csv", "ppp_factor_pca"), (PPP / "ppp_ipca_style_factor_returns.csv", "ppp_factor_ipca")]:
        if not path.exists():
            continue
        factors = read_indexed(path).apply(pd.to_numeric, errors="coerce")
        keep = [c for c in factors.columns if "full_diag" not in c]
        if not keep:
            continue
        f = factors[keep].shift(1).reset_index(names="date")
        ren = {c: f"{prefix}_{clean_name(c)}_lag1" for c in keep}
        f = f.rename(columns=ren)
        merged = df[["date"]].merge(f, on="date", how="left", sort=False)
        for old, new in ren.items():
            df[new] = merged[new].to_numpy()
            created.append(new)
            rows.append(
                {
                    "feature_name": new,
                    "source": str(path.relative_to(ROOT)),
                    "feature_family": "ppp_latent_factor_context",
                    "feature_type": "lagged_market_context",
                    "lag_rule": "PPP factor return shifted one week",
                    "used_in_models": True,
                    "leakage_check": "lagged factor context only",
                    "economic_interpretation": f"lagged PPP factor context from {old}",
                }
            )
    return created, rows


def feature_priority(col: str) -> int:
    name = col.lower()
    score = 0
    preferred = [
        "mom_13w",
        "mom_26w",
        "mom_52w",
        "vol_13w",
        "vol_26w",
        "drawdown_26w",
        "ma_distance_26w",
        "trend_consistency_13w",
        "rel_strength_spy_13w",
        "rel_strength_tlt_13w",
        "rel_strength_gld_13w",
        "rel_strength_hyg_13w",
        "rel_strength_lqd_13w",
        "l1_multi_horizon",
        "l1_xsmom",
        "l1_quality",
        "l1_bab",
        "l1_carry",
        "l1_reversal",
        "ooo2_leadlag",
        "ooo3_leadlag",
        "breadth",
        "market_trend",
        "market_drawdown",
        "recent_stress",
        "state_lag1",
        "ppp_factor",
        "proxy_",
    ]
    for i, key in enumerate(preferred):
        if key in name:
            score += 100 - i
    if name.startswith("z_"):
        score += 20
    if "full_diag" in name or "ggg1_etf_weight" in name:
        score -= 200
    return score


def select_model_features(df: pd.DataFrame, manifest: pd.DataFrame, generated_market_cols: list[str], state_cols: list[str]) -> tuple[list[str], list[str], pd.DataFrame]:
    excluded = {
        "date",
        "ticker",
        "market_state",
        "market_state_lag1",
        "risk_state_lag1",
        "ggg1_etf_weight",
    }
    excluded |= {c for c in df.columns if c.startswith("target_") or c.startswith("fwd_return_") or c.startswith("fwd_risk_adjusted_")}

    feature_manifest_rows = []
    ppp_etf_features = manifest[
        (manifest["entity_scope"].astype(str) == "ETF") & (manifest["feature_name"].isin(df.columns))
    ]["feature_name"].drop_duplicates().tolist()
    ppp_market_features = manifest[
        (manifest["entity_scope"].astype(str) == "MARKET") & (manifest["feature_name"].isin(df.columns))
    ]["feature_name"].drop_duplicates().tolist()

    etf_z_cols = []
    for col in ppp_etf_features:
        if col in excluded:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        if x.notna().mean() < 0.55 or x.nunique(dropna=True) < 8:
            continue
        z_col = f"z_{col}"
        df[z_col] = cross_sectional_z(df, col)
        if df[z_col].notna().mean() >= 0.55 and df[z_col].std(skipna=True) > 0:
            etf_z_cols.append(z_col)
            feature_manifest_rows.append(
                {
                    "feature_name": z_col,
                    "source": "ppp_panel_characteristics.csv",
                    "feature_family": classify_family(col),
                    "feature_type": "cross_sectional_zscore",
                    "lag_rule": "PPP source feature already lagged; z-score uses same-date cross-section only",
                    "used_in_models": True,
                    "leakage_check": "no forward returns; no future state",
                    "economic_interpretation": f"cross-sectional standardized {col}",
                }
            )

    market_cols = []
    for col in ppp_market_features + generated_market_cols:
        if col in excluded or col not in df.columns:
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        if x.notna().mean() < 0.50 or x.nunique(dropna=True) < 2:
            continue
        df[col] = winsorize_series(x)
        market_cols.append(col)
        feature_manifest_rows.append(
            {
                "feature_name": col,
                "source": "PPP/OOO/known proxy market context",
                "feature_family": classify_family(col),
                "feature_type": "lagged_market_or_signal_context",
                "lag_rule": "PPP manifest/source lagged or generated lagged context",
                "used_in_models": True,
                "leakage_check": "market context shifted before use when generated in QQQ",
                "economic_interpretation": col,
            }
        )

    for col in state_cols:
        feature_manifest_rows.append(
            {
                "feature_name": col,
                "source": "ppp_panel_characteristics.csv",
                "feature_family": "regime_state_context",
                "feature_type": "lagged_state_dummy",
                "lag_rule": "market_state_lag1 or risk_state_lag1 one-hot",
                "used_in_models": True,
                "leakage_check": "uses lagged state label only",
                "economic_interpretation": col.replace("state_lag1_", "lagged state: ").replace("risk_lag1_", "lagged risk state: "),
            }
        )

    all_base = sorted(set(etf_z_cols + market_cols + state_cols), key=lambda c: (-feature_priority(c), c))
    all_base = all_base[:MAX_BASE_FEATURES]
    selected_base = all_base[:MAX_MODEL_FEATURES_BASE]
    return all_base, selected_base, pd.DataFrame(feature_manifest_rows)


def safe_col(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index)


def add_explicit_interactions(df: pd.DataFrame) -> tuple[list[InteractionSpec], pd.DataFrame]:
    specs: list[InteractionSpec] = []

    def has(*cols: str) -> bool:
        return all(c in df.columns for c in cols)

    def add(name: str, left: str, right: str, formula: str, interpretation: str, event_func: Callable[[pd.DataFrame], pd.Series], family: str) -> None:
        if not has(left, right):
            return
        df[name] = (safe_col(df, left) * safe_col(df, right)).replace([np.inf, -np.inf], np.nan).clip(-8, 8)
        specs.append(InteractionSpec(name, left, right, formula, interpretation, event_func, family))

    state_recovery = "state_lag1_recovery_confirmed"
    state_fragile = "state_lag1_recovery_fragile"
    state_stress = "state_lag1_stressed_panic"
    state_calm = "state_lag1_calm_trend"
    state_neutral = "state_lag1_neutral_mixed"

    add(
        "int_mom13_x_lowvol13",
        "z_mom_13w",
        "z_vol_13w",
        "z_mom_13w > 0.5 and z_vol_13w < -0.5",
        "high 13w momentum with unusually low realized volatility",
        lambda d: (safe_col(d, "z_mom_13w") > 0.5) & (safe_col(d, "z_vol_13w") < -0.5),
        "momentum_x_volatility",
    )
    if "int_mom13_x_lowvol13" in df.columns:
        df["int_mom13_x_lowvol13"] *= -1.0

    add(
        "int_mom26_x_lowvol26",
        "z_mom_26w",
        "z_vol_26w",
        "z_mom_26w > 0.5 and z_vol_26w < -0.5",
        "high 26w momentum with low medium-horizon volatility",
        lambda d: (safe_col(d, "z_mom_26w") > 0.5) & (safe_col(d, "z_vol_26w") < -0.5),
        "momentum_x_volatility",
    )
    if "int_mom26_x_lowvol26" in df.columns:
        df["int_mom26_x_lowvol26"] *= -1.0

    add(
        "int_mom13_x_drawdown_repair",
        "z_mom_13w",
        "z_drawdown_26w",
        "z_mom_13w > 0.5 and z_drawdown_26w > 0.5",
        "positive momentum after relatively repaired drawdown",
        lambda d: (safe_col(d, "z_mom_13w") > 0.5) & (safe_col(d, "z_drawdown_26w") > 0.5),
        "momentum_x_drawdown",
    )
    add(
        "int_mom26_x_ma_distance26",
        "z_mom_26w",
        "z_ma_distance_26w",
        "z_mom_26w > 0.5 and z_ma_distance_26w > 0.5",
        "medium-horizon momentum confirmed by distance above moving average",
        lambda d: (safe_col(d, "z_mom_26w") > 0.5) & (safe_col(d, "z_ma_distance_26w") > 0.5),
        "momentum_x_trend",
    )
    add(
        "int_trend_consistency_x_lowdownsidevol",
        "z_trend_consistency_13w",
        "z_downside_vol_13w",
        "z_trend_consistency_13w > 0.5 and z_downside_vol_13w < -0.5",
        "consistent trend with muted downside volatility",
        lambda d: (safe_col(d, "z_trend_consistency_13w") > 0.5) & (safe_col(d, "z_downside_vol_13w") < -0.5),
        "trend_x_downside_risk",
    )
    if "int_trend_consistency_x_lowdownsidevol" in df.columns:
        df["int_trend_consistency_x_lowdownsidevol"] *= -1.0

    add(
        "int_credit_strength_x_trend",
        "ooo2_leadlag_HYG_minus_LQD_13w_signal",
        "z_ma_distance_26w",
        "HYG-LQD strength > 0 and z_ma_distance_26w > 0.5",
        "credit/risk appetite strength plus asset-specific trend confirmation",
        lambda d: (safe_col(d, "ooo2_leadlag_HYG_minus_LQD_13w_signal") > 0) & (safe_col(d, "z_ma_distance_26w") > 0.5),
        "credit_x_trend",
    )
    add(
        "int_market_trend_x_mom13",
        "ooo2_market_trend_positive_signal",
        "z_mom_13w",
        "market trend positive and z_mom_13w > 0.5",
        "market trend gate confirms asset momentum",
        lambda d: (safe_col(d, "ooo2_market_trend_positive_signal") > 0) & (safe_col(d, "z_mom_13w") > 0.5),
        "market_trend_x_momentum",
    )
    add(
        "int_breadth_x_mom13",
        "ooo2_breadth_ret13_positive_signal",
        "z_mom_13w",
        "breadth positive and z_mom_13w > 0.5",
        "cross-asset breadth confirms asset momentum",
        lambda d: (safe_col(d, "ooo2_breadth_ret13_positive_signal") > 0) & (safe_col(d, "z_mom_13w") > 0.5),
        "breadth_x_momentum",
    )
    add(
        "int_real_asset_strength_x_stress",
        "z_rel_strength_GLD_13w",
        state_stress,
        "lagged stressed_panic and z_rel_strength_GLD_13w > 0.5",
        "real-asset relative strength during lagged stress",
        lambda d: (safe_col(d, state_stress) > 0) & (safe_col(d, "z_rel_strength_GLD_13w") > 0.5),
        "real_asset_x_stress",
    )
    add(
        "int_international_strength_x_calm",
        "z_rel_strength_SPY_13w",
        state_calm,
        "lagged calm_trend and z_rel_strength_SPY_13w > 0.5",
        "asset leadership versus SPY during calm trend states",
        lambda d: (safe_col(d, state_calm) > 0) & (safe_col(d, "z_rel_strength_SPY_13w") > 0.5),
        "relative_strength_x_state",
    )
    add(
        "int_momentum_x_recovery_confirmed",
        "z_l1_multi_horizon_mom_multi_mom_equal_score_tradable",
        state_recovery,
        "lagged recovery_confirmed and Layer 1 multi-horizon momentum score > 0.5",
        "Layer 1 momentum active during confirmed recovery",
        lambda d: (safe_col(d, state_recovery) > 0) & (safe_col(d, "z_l1_multi_horizon_mom_multi_mom_equal_score_tradable") > 0.5),
        "layer1_momentum_x_state",
    )
    add(
        "int_momentum_x_recovery_fragile",
        "z_l1_multi_horizon_mom_multi_mom_equal_score_tradable",
        state_fragile,
        "lagged recovery_fragile and Layer 1 multi-horizon momentum score > 0.5",
        "Layer 1 momentum during fragile recovery",
        lambda d: (safe_col(d, state_fragile) > 0) & (safe_col(d, "z_l1_multi_horizon_mom_multi_mom_equal_score_tradable") > 0.5),
        "layer1_momentum_x_state",
    )
    add(
        "int_quality_x_highvol",
        "z_l1_quality_quality_score_tradable",
        "z_vol_13w",
        "Layer 1 quality score > 0.5 and z_vol_13w > 0.5",
        "quality selection when realized volatility is elevated",
        lambda d: (safe_col(d, "z_l1_quality_quality_score_tradable") > 0.5) & (safe_col(d, "z_vol_13w") > 0.5),
        "quality_x_volatility",
    )
    add(
        "int_bab_x_highvol",
        "z_l1_bab_bab_score_asset_class_neutral_tradable",
        "z_vol_13w",
        "asset-class-neutral BAB score > 0.5 and z_vol_13w > 0.5",
        "defensive BAB profile under high volatility",
        lambda d: (safe_col(d, "z_l1_bab_bab_score_asset_class_neutral_tradable") > 0.5) & (safe_col(d, "z_vol_13w") > 0.5),
        "bab_x_volatility",
    )
    add(
        "int_carry_x_lowvol",
        "z_l1_carry_carry_score_tradable",
        "z_vol_13w",
        "carry score > 0.5 and z_vol_13w < -0.5",
        "carry works best when volatility is controlled",
        lambda d: (safe_col(d, "z_l1_carry_carry_score_tradable") > 0.5) & (safe_col(d, "z_vol_13w") < -0.5),
        "carry_x_volatility",
    )
    if "int_carry_x_lowvol" in df.columns:
        df["int_carry_x_lowvol"] *= -1.0

    add(
        "int_reversal_x_drawdown",
        "z_l1_reversal_reversal_4w_score_tradable",
        "z_drawdown_26w",
        "4w reversal score > 0.5 and z_drawdown_26w < -0.5",
        "mean-reversion attempt in assets with relatively poor drawdowns",
        lambda d: (safe_col(d, "z_l1_reversal_reversal_4w_score_tradable") > 0.5) & (safe_col(d, "z_drawdown_26w") < -0.5),
        "reversal_x_drawdown",
    )
    add(
        "int_efa_spy_strength_x_market_trend",
        "ooo2_leadlag_EFA_minus_SPY_13w_signal",
        "ooo2_market_trend_positive_signal",
        "EFA-SPY lead/lag strength > 0 and market trend positive",
        "international leadership signal under positive market trend",
        lambda d: (safe_col(d, "ooo2_leadlag_EFA_minus_SPY_13w_signal") > 0) & (safe_col(d, "ooo2_market_trend_positive_signal") > 0),
        "ooo_leadlag_x_market_trend",
    )
    add(
        "int_gld_spy_strength_x_stress",
        "ooo2_leadlag_GLD_minus_SPY_13w_signal",
        state_stress,
        "GLD-SPY lead/lag strength > 0 and lagged stressed_panic",
        "gold leadership during lagged stress",
        lambda d: (safe_col(d, "ooo2_leadlag_GLD_minus_SPY_13w_signal") > 0) & (safe_col(d, state_stress) > 0),
        "ooo_leadlag_x_state",
    )
    add(
        "int_dba_spy_strength_x_inflation_proxy",
        "ooo2_leadlag_DBA_minus_SPY_13w_signal",
        "proxy_PDBC_ret_lag1",
        "DBA-SPY strength > 0 and lagged PDBC return > 0",
        "agriculture/commodity leadership confirmed by broad commodity return",
        lambda d: (safe_col(d, "ooo2_leadlag_DBA_minus_SPY_13w_signal") > 0) & (safe_col(d, "proxy_PDBC_ret_lag1") > 0),
        "real_asset_x_inflation_proxy",
    )
    add(
        "int_ppp_equity_factor_x_lowvol_mom",
        "ppp_factor_pca_pca_exp_f1_lag1",
        "int_mom13_x_lowvol13",
        "lagged PPP equity factor positive and high momentum/low vol event",
        "PPP equity factor context gated by asset-specific momentum/low-vol interaction",
        lambda d: (safe_col(d, "ppp_factor_pca_pca_exp_f1_lag1") > 0) & (safe_col(d, "z_mom_13w") > 0.5) & (safe_col(d, "z_vol_13w") < -0.5),
        "ppp_factor_x_asset_interaction",
    )
    add(
        "int_ppp_duration_factor_x_quality",
        "ppp_factor_pca_pca_exp_f2_lag1",
        "z_l1_quality_quality_score_tradable",
        "lagged PPP duration/defense factor positive and quality score > 0.5",
        "quality selection when PPP duration/defensive factor is favorable",
        lambda d: (safe_col(d, "ppp_factor_pca_pca_exp_f2_lag1") > 0) & (safe_col(d, "z_l1_quality_quality_score_tradable") > 0.5),
        "ppp_factor_x_quality",
    )
    add(
        "int_breadth_recovery_x_mom13",
        "ooo2_breadth_ret13_positive_x_recovery_confirmed_signal",
        "z_mom_13w",
        "OOO breadth recovery signal active and z_mom_13w > 0.5",
        "recovery-confirmed breadth with ETF momentum",
        lambda d: (safe_col(d, "ooo2_breadth_ret13_positive_x_recovery_confirmed_signal") > 0) & (safe_col(d, "z_mom_13w") > 0.5),
        "ooo_state_breadth_x_momentum",
    )
    add(
        "int_calm_neutral_trend_x_relspy",
        "ooo3event_market_trend_calm_neutral_event",
        "z_rel_strength_SPY_13w",
        "OOO calm/neutral trend event and ETF relative strength vs SPY > 0.5",
        "asset relative leadership during calm/neutral trend windows",
        lambda d: (safe_col(d, "ooo3event_market_trend_calm_neutral_event") > 0) & (safe_col(d, "z_rel_strength_SPY_13w") > 0.5),
        "ooo_event_x_relative_strength",
    )

    rows = []
    for spec in specs:
        rows.append(
            {
                "feature_name": spec.feature_name,
                "source": "QQQ explicit economic interaction",
                "feature_family": spec.family,
                "feature_type": "explicit_pairwise_interaction",
                "lag_rule": "both legs are lagged PPP or generated lagged context",
                "used_in_models": True,
                "leakage_check": "no target/future return/state input",
                "economic_interpretation": spec.economic_interpretation,
                "left_feature": spec.left,
                "right_feature": spec.right,
                "rule_formula": spec.formula,
            }
        )
    return specs, pd.DataFrame(rows)


def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[InteractionSpec], list[str], list[str]]:
    returns, characteristics, ppp_manifest = load_ppp_inputs()
    df = characteristics.copy()
    tickers = [c for c in returns.columns if c != "date"]

    for horizon in [4, 8]:
        fwd = forward_compound_returns(returns, horizon).stack(dropna=False).rename(f"fwd_return_{horizon}w").reset_index()
        fwd.columns = ["date", "ticker", f"fwd_return_{horizon}w"]
        df = df.merge(fwd, on=["date", "ticker"], how="left", sort=False)

    vol_for_ra = pd.to_numeric(df.get("vol_13w"), errors="coerce").replace(0.0, np.nan)
    for horizon in [4, 8]:
        df[f"fwd_risk_adjusted_return_{horizon}w"] = df[f"fwd_return_{horizon}w"] / vol_for_ra.clip(lower=0.002)
        df[f"target_etf_forward_top_quantile_{horizon}w"] = add_top_quantile_target(df, f"fwd_return_{horizon}w", f"target_etf_forward_top_quantile_{horizon}w")
        df[f"target_etf_forward_risk_adjusted_top_quantile_{horizon}w"] = add_top_quantile_target(
            df,
            f"fwd_risk_adjusted_return_{horizon}w",
            f"target_etf_forward_risk_adjusted_top_quantile_{horizon}w",
        )

    state_cols = build_state_dummies(df)
    market_context_cols, market_context_manifest = add_market_context(df, returns)
    all_base_cols, selected_base_cols, base_manifest = select_model_features(df, ppp_manifest, market_context_cols, state_cols)
    interaction_specs, interaction_manifest = add_explicit_interactions(df)
    interaction_cols = [s.feature_name for s in interaction_specs]
    feature_cols_with_interactions = (selected_base_cols + interaction_cols)[:MAX_MODEL_FEATURES_WITH_INTERACTIONS]

    feature_manifest = pd.concat([base_manifest, pd.DataFrame(market_context_manifest), interaction_manifest], ignore_index=True)
    feature_manifest = feature_manifest.drop_duplicates("feature_name")
    feature_manifest["missingness"] = feature_manifest["feature_name"].map(df.isna().mean()).astype(float)
    feature_manifest["non_missing_rows"] = feature_manifest["feature_name"].map(df.notna().sum()).astype(float)
    feature_manifest["selected_base_model"] = feature_manifest["feature_name"].isin(selected_base_cols)
    feature_manifest["selected_interaction_model"] = feature_manifest["feature_name"].isin(feature_cols_with_interactions)

    id_cols = ["date", "ticker", "market_state", "market_state_lag1", "risk_state_lag1"]
    outcome_cols = [c for c in df.columns if c.startswith("fwd_return_") or c.startswith("fwd_risk_adjusted_return_") or c.startswith("target_")]
    keep_cols = [c for c in id_cols if c in df.columns] + all_base_cols + interaction_cols + outcome_cols
    out_df = df[keep_cols].sort_values(["date", "ticker"]).reset_index(drop=True)

    save_csv(out_df, OUT / "qqq_ml_dataset.csv")
    sample = pd.concat([out_df.head(1000), out_df.tail(1000)], ignore_index=True).drop_duplicates(["date", "ticker"])
    save_csv(sample, OUT / "qqq_ml_dataset_sample.csv")
    save_csv(feature_manifest, OUT / "qqq_feature_manifest.csv")

    schema = {
        "rows": int(out_df.shape[0]),
        "columns": int(out_df.shape[1]),
        "date_range": [str(out_df["date"].min().date()), str(out_df["date"].max().date())],
        "id_columns": [c for c in id_cols if c in out_df.columns],
        "target_columns": TARGETS,
        "forward_return_columns": [c for c in outcome_cols if c.startswith("fwd_")],
        "base_feature_count": int(len(selected_base_cols)),
        "interaction_feature_count": int(len(interaction_cols)),
        "feature_columns_base_model": selected_base_cols,
        "feature_columns_interaction_model": feature_cols_with_interactions,
    }
    (OUT / "qqq_dataset_schema.json").write_text(json.dumps(schema, indent=2))

    target_summary = target_balance_summary(out_df)
    save_csv(target_summary, OUT / "qqq_target_summary.csv")
    data_quality = data_quality_report(out_df, selected_base_cols, interaction_cols)
    save_csv(data_quality, OUT / "qqq_data_quality_report.csv")
    leakage = leakage_checklist(out_df, feature_manifest)
    save_csv(leakage, OUT / "qqq_leakage_checklist.csv")
    return out_df, feature_manifest, target_summary, interaction_specs, selected_base_cols, feature_cols_with_interactions


def target_balance_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target in TARGETS:
        valid = df[df[target].notna()].copy()
        rows.append(
            {
                "target": target,
                "entity_type": "ETF",
                "n_observations": int(len(valid)),
                "positive_rate": float(valid[target].mean()) if len(valid) else np.nan,
                "start_date": valid["date"].min().date() if len(valid) else "",
                "end_date": valid["date"].max().date() if len(valid) else "",
                "enough_samples": bool(len(valid) >= 5000 and valid[target].sum() >= 500),
                "definition": TARGET_META[target]["target_type"],
                "horizon_weeks": TARGET_META[target]["horizon"],
            }
        )
        for state, g in valid.groupby("market_state"):
            rows.append(
                {
                    "target": f"{target}__state_{state}",
                    "entity_type": "ETF_STATE_SUBSET",
                    "n_observations": int(len(g)),
                    "positive_rate": float(g[target].mean()) if len(g) else np.nan,
                    "start_date": g["date"].min().date() if len(g) else "",
                    "end_date": g["date"].max().date() if len(g) else "",
                    "enough_samples": bool(len(g) >= 500 and g[target].sum() >= 50),
                    "definition": "state-specific diagnostic target balance only",
                    "horizon_weeks": TARGET_META[target]["horizon"],
                }
            )
    rows.append(
        {
            "target": "optional_sleeve_component_opportunity",
            "entity_type": "SLEEVE",
            "n_observations": 0,
            "positive_rate": np.nan,
            "start_date": "",
            "end_date": "",
            "enough_samples": False,
            "definition": "not built in QQQ because PPP source is ETF-level and clean sleeve/component opportunity labels require a separate RRR sleeve meta-labeling panel",
            "horizon_weeks": np.nan,
        }
    )
    return pd.DataFrame(rows)


def data_quality_report(df: pd.DataFrame, base_cols: list[str], interaction_cols: list[str]) -> pd.DataFrame:
    rows = [
        {"section": "dataset", "item": "date_range", "metric": "value", "value": f"{df['date'].min().date()} to {df['date'].max().date()}", "notes": ""},
        {"section": "dataset", "item": "rows", "metric": "count", "value": int(df.shape[0]), "notes": "ETF-date rows"},
        {"section": "dataset", "item": "tickers", "metric": "count", "value": int(df["ticker"].nunique()), "notes": ",".join(sorted(df["ticker"].dropna().unique())[:40])},
        {"section": "dataset", "item": "base_features", "metric": "count", "value": len(base_cols), "notes": "selected for base models"},
        {"section": "dataset", "item": "interaction_features", "metric": "count", "value": len(interaction_cols), "notes": "explicit economic interaction set"},
    ]
    for col in base_cols + interaction_cols:
        rows.append(
            {
                "section": "feature_missingness",
                "item": col,
                "metric": "missingness",
                "value": float(df[col].isna().mean()),
                "notes": classify_family(col),
            }
        )
    return pd.DataFrame(rows)


def leakage_checklist(df: pd.DataFrame, feature_manifest: pd.DataFrame) -> pd.DataFrame:
    checks = [
        ("all_ppp_source_features_lagged", True, "PPP manifest states rolling/Layer1/OOO features are lagged."),
        ("qqq_generated_proxy_features_lagged", True, "Known proxy and PPP factor context shifted one week."),
        ("target_columns_excluded_from_feature_list", True, "Feature manifest excludes target/fwd_return columns."),
        ("current_market_state_not_live_feature", True, "Current market_state retained only for validation grouping; live state dummies use lag1."),
        ("no_forward_returns_as_features", not any(c.startswith("fwd_") for c in feature_manifest["feature_name"]), "Forward returns are target/outcome columns only."),
        ("no_random_splits", True, "Walk-forward expanding dates only."),
        ("no_centered_windows", True, "QQQ uses PPP trailing features and same-date cross-sectional z-scores."),
        ("no_production_or_shadow_change", True, f"production={PRODUCTION}; shadow={SHADOW}; GGG1={GGG1}."),
        ("dataset_has_targets", all(df[t].notna().sum() > 0 for t in TARGETS), "All four requested ETF targets exist."),
    ]
    return pd.DataFrame([{"check": c, "passed": bool(p), "note": n} for c, p, n in checks])


def build_walkforward_splits(df: pd.DataFrame) -> pd.DataFrame:
    dates = pd.Index(sorted(pd.to_datetime(df["date"].dropna().unique())))
    rows = []
    split_id = 0
    for start_idx in range(INITIAL_TRAIN_DATES, len(dates), REFIT_FREQ):
        test_end_idx = min(start_idx + REFIT_FREQ, len(dates))
        train_dates = dates[:start_idx]
        test_dates = dates[start_idx:test_end_idx]
        if len(test_dates) == 0:
            continue
        rows.append(
            {
                "split_id": split_id,
                "train_start_date": train_dates[0],
                "train_end_date": train_dates[-1],
                "test_start_date": test_dates[0],
                "test_end_date": test_dates[-1],
                "n_train_dates": len(train_dates),
                "n_test_dates": len(test_dates),
            }
        )
        split_id += 1
    splits = pd.DataFrame(rows)
    save_csv(splits, OUT / "qqq_walkforward_splits.csv")
    return splits


def make_model(model_name: str) -> Pipeline:
    if model_name in {"logistic_l2_base", "logistic_l2_interactions"}:
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(C=0.35, max_iter=600, solver="lbfgs", random_state=RANDOM_STATE)),
            ]
        )
    if model_name == "decision_tree_depth3":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", DecisionTreeClassifier(max_depth=3, min_samples_leaf=90, random_state=RANDOM_STATE)),
            ]
        )
    if model_name == "random_forest_depth4":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=90,
                        max_depth=4,
                        min_samples_leaf=80,
                        max_features="sqrt",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        )
    if model_name == "hist_gradient_depth3":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        max_iter=90,
                        learning_rate=0.055,
                        max_leaf_nodes=15,
                        min_samples_leaf=80,
                        l2_regularization=0.05,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        )
    raise ValueError(model_name)


def predict_baselines(train: pd.DataFrame, test: pd.DataFrame, target: str) -> list[pd.DataFrame]:
    rows = []
    y_train = pd.to_numeric(train[target], errors="coerce")
    train_rate = float(y_train.mean()) if y_train.notna().any() else np.nan
    base = test[["date", "ticker", "market_state", target, TARGET_META[target]["return_col"]]].copy()
    base = base.rename(columns={target: "actual", TARGET_META[target]["return_col"]: "forward_return"})

    naive = base.copy()
    naive["model"] = "naive_historical_class_rate"
    naive["prediction"] = train_rate
    rows.append(naive)

    if "market_state_lag1" in train.columns:
        state_rates = train.groupby("market_state_lag1")[target].mean()
        state = base.copy()
        state["model"] = "state_only_lag1_rate"
        state["prediction"] = test["market_state_lag1"].map(state_rates).fillna(train_rate).to_numpy()
        rows.append(state)

    mom_feature = "z_mom_13w" if "z_mom_13w" in test.columns else "z_mom_26w"
    if mom_feature in test.columns:
        mom = base.copy()
        mom["model"] = "simple_momentum_rank"
        mom["prediction"] = test.groupby("date")[mom_feature].rank(pct=True).fillna(train_rate).to_numpy()
        rows.append(mom)

    return rows


def feature_importance_from_pipeline(pipe: Pipeline, feature_cols: list[str], model_name: str) -> pd.DataFrame:
    model = pipe.named_steps["model"]
    rows = []
    if hasattr(model, "coef_"):
        coefs = pd.Series(model.coef_[0], index=feature_cols)
        top = coefs.abs().sort_values(ascending=False).head(MAX_IMPORTANCE_ROWS_PER_FOLD).index
        for feature in top:
            rows.append(
                {
                    "feature": feature,
                    "importance": float(coefs.loc[feature]),
                    "abs_importance": float(abs(coefs.loc[feature])),
                    "importance_type": "coefficient",
                    "model": model_name,
                }
            )
    elif hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_cols)
        top = imp.sort_values(ascending=False).head(MAX_IMPORTANCE_ROWS_PER_FOLD)
        for feature, value in top.items():
            if value <= 0:
                continue
            rows.append(
                {
                    "feature": feature,
                    "importance": float(value),
                    "abs_importance": float(abs(value)),
                    "importance_type": "gini_or_split_importance",
                    "model": model_name,
                }
            )
    return pd.DataFrame(rows)


def tree_path_pairs_from_estimator(estimator, feature_cols: list[str], max_estimators: int = 30) -> list[dict]:
    rows = []

    def walk_tree(tree_est, model_label: str) -> None:
        tree = tree_est.tree_

        def recurse(node: int, path: list[str]) -> None:
            if tree.feature[node] == _tree.TREE_UNDEFINED:
                unique = list(dict.fromkeys(path))
                for i in range(len(unique)):
                    for j in range(i + 1, len(unique)):
                        rows.append(
                            {
                                "left_feature": unique[i],
                                "right_feature": unique[j],
                                "path_depth": len(unique),
                                "leaf_weighted_samples": float(tree.weighted_n_node_samples[node]),
                                "source_tree": model_label,
                            }
                        )
                return
            feat = feature_cols[tree.feature[node]]
            recurse(tree.children_left[node], path + [feat])
            recurse(tree.children_right[node], path + [feat])

        recurse(0, [])

    if isinstance(estimator, DecisionTreeClassifier):
        walk_tree(estimator, "decision_tree")
    elif isinstance(estimator, RandomForestClassifier):
        for k, tree_est in enumerate(estimator.estimators_[:max_estimators]):
            walk_tree(tree_est, f"rf_tree_{k}")
    return rows


def run_walkforward_models(
    df: pd.DataFrame,
    splits: pd.DataFrame,
    base_features: list[str],
    interaction_features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prediction_frames = []
    importance_rows = []
    tree_pair_rows = []
    model_specs = [
        ("logistic_l2_base", base_features),
        ("logistic_l2_interactions", interaction_features),
        ("decision_tree_depth3", interaction_features),
        ("random_forest_depth4", interaction_features),
        ("hist_gradient_depth3", interaction_features),
    ]

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for target in TARGETS:
        for _, split in splits.iterrows():
            train_mask = (df["date"] <= split["train_end_date"]) & df[target].notna()
            test_mask = (df["date"] >= split["test_start_date"]) & (df["date"] <= split["test_end_date"]) & df[target].notna()
            train = df.loc[train_mask].copy()
            test = df.loc[test_mask].copy()
            if len(train) < 2000 or len(test) < 50 or train[target].nunique() < 2:
                continue
            for baseline in predict_baselines(train, test, target):
                baseline["target"] = target
                baseline["split_id"] = int(split["split_id"])
                prediction_frames.append(baseline[["date", "ticker", "market_state", "target", "model", "split_id", "prediction", "actual", "forward_return"]])

            for model_name, cols in model_specs:
                usable = [c for c in cols if c in df.columns and train[c].notna().any()]
                x_train = train[usable].apply(pd.to_numeric, errors="coerce")
                y_train = train[target].astype(int)
                x_test = test[usable].apply(pd.to_numeric, errors="coerce")
                if y_train.nunique() < 2 or not usable:
                    continue
                pipe = make_model(model_name)
                try:
                    pipe.fit(x_train, y_train)
                    pred = pipe.predict_proba(x_test)[:, 1]
                except Exception as exc:
                    importance_rows.append(
                        {
                            "target": target,
                            "model": model_name,
                            "split_id": int(split["split_id"]),
                            "feature": "MODEL_FIT_ERROR",
                            "importance": np.nan,
                            "abs_importance": np.nan,
                            "importance_type": f"error: {exc}",
                            "feature_family": "error",
                        }
                    )
                    continue
                out = test[["date", "ticker", "market_state", target, TARGET_META[target]["return_col"]]].copy()
                out = out.rename(columns={target: "actual", TARGET_META[target]["return_col"]: "forward_return"})
                out["target"] = target
                out["model"] = model_name
                out["split_id"] = int(split["split_id"])
                out["prediction"] = pred
                prediction_frames.append(out[["date", "ticker", "market_state", "target", "model", "split_id", "prediction", "actual", "forward_return"]])

                imp = feature_importance_from_pipeline(pipe, usable, model_name)
                for _, row in imp.iterrows():
                    importance_rows.append(
                        {
                            "target": target,
                            "model": model_name,
                            "split_id": int(split["split_id"]),
                            "feature": row["feature"],
                            "importance": row["importance"],
                            "abs_importance": row["abs_importance"],
                            "importance_type": row["importance_type"],
                            "feature_family": classify_family(row["feature"]),
                        }
                    )
                if model_name in {"decision_tree_depth3", "random_forest_depth4"}:
                    model = pipe.named_steps["model"]
                    for pair in tree_path_pairs_from_estimator(model, usable):
                        pair.update({"target": target, "model": model_name, "split_id": int(split["split_id"])})
                        tree_pair_rows.append(pair)

    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    importance = pd.DataFrame(importance_rows)
    tree_pairs = pd.DataFrame(tree_pair_rows)
    save_csv(predictions, OUT / "qqq_model_predictions.csv")
    save_csv(importance, OUT / "qqq_feature_importance.csv")
    save_csv(tree_pairs, OUT / "qqq_tree_path_interaction_pairs.csv")
    return predictions, importance, tree_pairs


def safe_auc(y: pd.Series, p: pd.Series) -> float:
    if y.nunique(dropna=True) < 2:
        return np.nan
    try:
        return float(roc_auc_score(y, p))
    except Exception:
        return np.nan


def datewise_rank_metrics(g: pd.DataFrame) -> dict[str, float]:
    ic_rows = []
    spread_rows = []
    precision_rows = []
    for _, d in g.groupby("date"):
        if d["prediction"].notna().sum() < 8 or d["actual"].nunique(dropna=True) < 2:
            continue
        pearson = d["prediction"].corr(d["forward_return"])
        spearman = d["prediction"].corr(d["forward_return"], method="spearman")
        n = max(2, int(math.ceil(len(d) * 0.10)))
        top = d.sort_values("prediction", ascending=False).head(n)
        bottom = d.sort_values("prediction", ascending=True).head(n)
        spread_rows.append(float(top["forward_return"].mean() - bottom["forward_return"].mean()))
        precision_rows.append(float(top["actual"].mean()))
        ic_rows.append((pearson, spearman))
    if not ic_rows:
        return {"pearson_ic": np.nan, "spearman_ic": np.nan, "positive_spearman_ic_rate": np.nan, "top_minus_bottom_forward_return_spread": np.nan, "top_decile_precision": np.nan}
    ic = pd.DataFrame(ic_rows, columns=["pearson_ic", "spearman_ic"])
    return {
        "pearson_ic": float(ic["pearson_ic"].mean()),
        "spearman_ic": float(ic["spearman_ic"].mean()),
        "positive_spearman_ic_rate": float((ic["spearman_ic"] > 0).mean()),
        "top_minus_bottom_forward_return_spread": float(np.nanmean(spread_rows)),
        "top_decile_precision": float(np.nanmean(precision_rows)),
    }


def evaluate_predictions(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    if predictions.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty
    pred = predictions.copy()
    pred["actual"] = pd.to_numeric(pred["actual"], errors="coerce")
    pred["prediction"] = pd.to_numeric(pred["prediction"], errors="coerce").clip(1e-6, 1 - 1e-6)
    pred["forward_return"] = pd.to_numeric(pred["forward_return"], errors="coerce")
    for (target, model), g in pred.groupby(["target", "model"]):
        g = g.dropna(subset=["actual", "prediction"])
        if g.empty:
            continue
        rank = datewise_rank_metrics(g)
        rows.append(
            {
                "target": target,
                "model": model,
                "n_oos": int(len(g)),
                "positive_rate": float(g["actual"].mean()),
                "brier": float(brier_score_loss(g["actual"], g["prediction"])),
                "auc": safe_auc(g["actual"], g["prediction"]),
                "log_loss": float(log_loss(g["actual"], g["prediction"], labels=[0, 1])),
                **rank,
            }
        )
    metrics = pd.DataFrame(rows)
    baseline = metrics[metrics["model"].isin(["naive_historical_class_rate", "state_only_lag1_rate", "simple_momentum_rank"])].copy()
    save_csv(metrics, OUT / "qqq_model_metrics.csv")
    save_csv(baseline, OUT / "qqq_baseline_model_metrics.csv")

    calibration_rows = []
    for (target, model), g in pred.groupby(["target", "model"]):
        g = g.dropna(subset=["actual", "prediction"])
        if len(g) < 100:
            continue
        bins = pd.qcut(g["prediction"].rank(method="first"), 10, labels=False, duplicates="drop")
        for b, h in g.groupby(bins):
            calibration_rows.append(
                {
                    "target": target,
                    "model": model,
                    "bucket": int(b),
                    "n": int(len(h)),
                    "avg_prediction": float(h["prediction"].mean()),
                    "actual_rate": float(h["actual"].mean()),
                    "avg_forward_return": float(h["forward_return"].mean()),
                }
            )
    calibration = pd.DataFrame(calibration_rows)
    save_csv(calibration, OUT / "qqq_calibration_summary.csv")

    state_rows = []
    for (target, model, state), g in pred.groupby(["target", "model", "market_state"]):
        if len(g) < 50:
            continue
        rank = datewise_rank_metrics(g)
        state_rows.append(
            {
                "target": target,
                "model": model,
                "market_state": state,
                "n_oos": int(len(g)),
                "positive_rate": float(g["actual"].mean()),
                "brier": float(brier_score_loss(g["actual"], g["prediction"])),
                "auc": safe_auc(g["actual"], g["prediction"]),
                **rank,
            }
        )
    state_perf = pd.DataFrame(state_rows)
    save_csv(state_perf, OUT / "qqq_state_specific_model_performance.csv")

    sub_rows = []
    periods = [
        ("2010_2015", pd.Timestamp("2010-01-01"), pd.Timestamp("2015-12-31")),
        ("2016_2020", pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31")),
        ("2021_2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-12-31")),
    ]
    pred["date"] = pd.to_datetime(pred["date"])
    for (target, model), g in pred.groupby(["target", "model"]):
        for period, start, end in periods:
            h = g[(g["date"] >= start) & (g["date"] <= end)].dropna(subset=["actual", "prediction"])
            if len(h) < 100:
                continue
            rank = datewise_rank_metrics(h)
            sub_rows.append(
                {
                    "target": target,
                    "model": model,
                    "subperiod": period,
                    "n_oos": int(len(h)),
                    "brier": float(brier_score_loss(h["actual"], h["prediction"])),
                    "auc": safe_auc(h["actual"], h["prediction"]),
                    **rank,
                }
            )
    subperiod = pd.DataFrame(sub_rows)
    save_csv(subperiod, OUT / "qqq_subperiod_stability.csv")
    return metrics, baseline, calibration, state_perf, subperiod


def aggregate_importance(importance: pd.DataFrame, tree_pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if importance.empty:
        family = pd.DataFrame()
        interaction = pd.DataFrame()
    else:
        family = (
            importance.groupby(["target", "model", "feature_family"])
            .agg(mean_abs_importance=("abs_importance", "mean"), n_refits=("split_id", "nunique"), feature_count=("feature", "nunique"))
            .reset_index()
            .sort_values(["target", "mean_abs_importance"], ascending=[True, False])
        )
        save_csv(family, OUT / "qqq_feature_family_importance.csv")
        explicit = importance[importance["feature"].str.startswith("int_", na=False)].copy()
        if not explicit.empty:
            explicit["positive_sign"] = explicit["importance"] > 0
            interaction = (
                explicit.groupby(["target", "feature"])
                .agg(
                    mean_importance=("importance", "mean"),
                    mean_abs_importance=("abs_importance", "mean"),
                    sign_stability=("positive_sign", lambda x: max(float(x.mean()), float((~x).mean()))),
                    n_models=("model", "nunique"),
                    n_refits=("split_id", "nunique"),
                )
                .reset_index()
            )
        else:
            interaction = pd.DataFrame()
    if not tree_pairs.empty:
        pair = (
            tree_pairs.groupby(["target", "left_feature", "right_feature"])
            .agg(path_cooccurrence_count=("source_tree", "count"), avg_leaf_weighted_samples=("leaf_weighted_samples", "mean"), n_refits=("split_id", "nunique"))
            .reset_index()
        )
        pair["feature"] = pair["left_feature"] + "__PAIR__" + pair["right_feature"]
        pair["mean_importance"] = pair["path_cooccurrence_count"]
        pair["mean_abs_importance"] = pair["path_cooccurrence_count"]
        pair["sign_stability"] = np.nan
        pair["n_models"] = np.nan
        pair["interaction_source"] = "tree_path_pair"
        if interaction.empty:
            interaction = pair[["target", "feature", "mean_importance", "mean_abs_importance", "sign_stability", "n_models", "n_refits", "interaction_source"]]
        else:
            interaction["interaction_source"] = "explicit_interaction_feature"
            interaction = pd.concat(
                [interaction, pair[["target", "feature", "mean_importance", "mean_abs_importance", "sign_stability", "n_models", "n_refits", "interaction_source"]]],
                ignore_index=True,
            )
    else:
        if not interaction.empty:
            interaction["interaction_source"] = "explicit_interaction_feature"
    if not interaction.empty:
        interaction = interaction.sort_values(["target", "mean_abs_importance"], ascending=[True, False])
    save_csv(interaction, OUT / "qqq_interaction_importance.csv")
    return family, interaction


def evaluate_rule_event(df: pd.DataFrame, event: pd.Series, target: str, dates_oos: pd.Series) -> dict[str, float]:
    meta = TARGET_META[target]
    mask = df["date"].isin(dates_oos) & df[target].notna() & event.fillna(False)
    base_mask = df["date"].isin(dates_oos) & df[target].notna()
    g = df.loc[mask]
    base = df.loc[base_mask]
    if base.empty:
        return {}
    n_events = int(len(g))
    freq = float(n_events / len(base)) if len(base) else np.nan
    precision = float(g[target].mean()) if n_events else np.nan
    base_precision = float(base[target].mean()) if len(base) else np.nan
    avg_ret = float(g[meta["return_col"]].mean()) if n_events else np.nan
    base_ret = float(base[meta["return_col"]].mean()) if len(base) else np.nan
    return {
        "n_events": n_events,
        "event_frequency": freq,
        "precision": precision,
        "baseline_precision": base_precision,
        "precision_lift": precision - base_precision if np.isfinite(precision) and np.isfinite(base_precision) else np.nan,
        "avg_forward_return": avg_ret,
        "baseline_avg_forward_return": base_ret,
        "return_lift": avg_ret - base_ret if np.isfinite(avg_ret) and np.isfinite(base_ret) else np.nan,
    }


def rule_discovery(
    df: pd.DataFrame,
    specs: list[InteractionSpec],
    interaction_importance: pd.DataFrame,
    splits: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    oos_dates = pd.to_datetime(df["date"].unique())
    first_oos = pd.to_datetime(splits["test_start_date"]).min()
    oos_dates = oos_dates[oos_dates >= first_oos]
    importance_lookup = {}
    if not interaction_importance.empty:
        explicit = interaction_importance[interaction_importance["interaction_source"] == "explicit_interaction_feature"]
        for (target, feature), g in explicit.groupby(["target", "feature"]):
            importance_lookup[(target, feature)] = float(g["mean_abs_importance"].mean())

    rule_rows = []
    perf_rows = []
    state_rows = []
    stability_rows = []
    periods = [
        ("2010_2015", pd.Timestamp("2010-01-01"), pd.Timestamp("2015-12-31")),
        ("2016_2020", pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-31")),
        ("2021_2026", pd.Timestamp("2021-01-01"), pd.Timestamp("2026-12-31")),
    ]
    for spec in specs:
        event = spec.event_func(df).fillna(False).astype(bool)
        for target in TARGETS:
            stats = evaluate_rule_event(df, event, target, oos_dates)
            if not stats:
                continue
            rule_name = f"rule_{spec.feature_name}__{target.replace('target_etf_', '')}"
            imp = importance_lookup.get((target, spec.feature_name), np.nan)
            rule_rows.append(
                {
                    "rule_name": rule_name,
                    "interaction_feature": spec.feature_name,
                    "features_used": f"{spec.left}|{spec.right}",
                    "rule_formula": spec.formula,
                    "economic_interpretation": spec.economic_interpretation,
                    "target": target,
                    "model_source": "explicit_interaction_feature plus nonlinear model importance",
                    "oos_metric_lift": stats.get("return_lift"),
                    "event_frequency": stats.get("event_frequency"),
                    "stability": np.nan,
                    "redundancy_warning": "",
                    "next_recommended_phase": "",
                    "mean_abs_model_importance": imp,
                }
            )
            perf_rows.append({"rule_name": rule_name, "target": target, **stats})
            for state, g in df[df["date"].isin(oos_dates) & df[target].notna()].groupby("market_state"):
                state_event = event.reindex(g.index).fillna(False)
                if len(g) < 100:
                    continue
                sg = g[state_event]
                state_rows.append(
                    {
                        "rule_name": rule_name,
                        "target": target,
                        "market_state": state,
                        "n_state_obs": int(len(g)),
                        "n_events": int(len(sg)),
                        "event_frequency": float(len(sg) / len(g)) if len(g) else np.nan,
                        "precision": float(sg[target].mean()) if len(sg) else np.nan,
                        "baseline_precision": float(g[target].mean()) if len(g) else np.nan,
                        "precision_lift": (float(sg[target].mean()) - float(g[target].mean())) if len(sg) else np.nan,
                        "avg_forward_return": float(sg[TARGET_META[target]["return_col"]].mean()) if len(sg) else np.nan,
                        "baseline_avg_forward_return": float(g[TARGET_META[target]["return_col"]].mean()) if len(g) else np.nan,
                    }
                )
            for period, start, end in periods:
                period_dates = oos_dates[(oos_dates >= start) & (oos_dates <= end)]
                st = evaluate_rule_event(df, event, target, period_dates)
                if st:
                    stability_rows.append({"rule_name": rule_name, "target": target, "subperiod": period, **st})

    rules = pd.DataFrame(rule_rows)
    perf = pd.DataFrame(perf_rows)
    state_rules = pd.DataFrame(state_rows)
    stability = pd.DataFrame(stability_rows)
    if not stability.empty:
        agg = stability.groupby("rule_name").agg(
            subperiods_with_events=("n_events", lambda x: int((x >= 20).sum())),
            positive_return_lift_share=("return_lift", lambda x: float((x > 0).mean())),
            positive_precision_lift_share=("precision_lift", lambda x: float((x > 0).mean())),
            min_subperiod_events=("n_events", "min"),
        )
        if not rules.empty:
            rules = rules.merge(agg.reset_index(), on="rule_name", how="left")
            rules["stability"] = rules[["positive_return_lift_share", "positive_precision_lift_share"]].mean(axis=1)
    save_csv(rules, OUT / "qqq_extracted_interaction_rules.csv")
    save_csv(perf, OUT / "qqq_rule_performance_summary.csv")
    save_csv(state_rules, OUT / "qqq_state_specific_rules.csv")
    save_csv(stability, OUT / "qqq_rule_stability.csv")
    return rules, perf, state_rules, stability


def redundancy_and_incrementality(
    df: pd.DataFrame,
    specs: list[InteractionSpec],
    rules: pd.DataFrame,
    perf: pd.DataFrame,
    stability: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if rules.empty:
        empty = pd.DataFrame()
        save_csv(empty, OUT / "qqq_redundancy_summary.csv")
        save_csv(empty, OUT / "qqq_incrementality_summary.csv")
        save_csv(empty, OUT / "qqq_rule_event_overlap.csv")
        return empty, empty, empty
    spec_map = {s.feature_name: s for s in specs}
    comp_cols = [
        c
        for c in df.columns
        if c.startswith("ooo2_")
        or c.startswith("ooo3_")
        or c.startswith("ooo3event_")
        or c.startswith("state_lag1_")
        or c.startswith("risk_lag1_")
        or c.startswith("ppp_factor_")
        or c.startswith("proxy_")
        or c.startswith("z_l1_")
        or c in {"regime_market_trend_positive", "regime_market_drawdown", "regime_recent_stress_26w"}
    ]
    red_rows = []
    overlap_rows = []
    inc_rows = []
    first_oos_date = pd.Timestamp("2010-01-01")
    for _, rule in rules.iterrows():
        spec = spec_map.get(rule["interaction_feature"])
        if spec is None:
            continue
        event = spec.event_func(df).fillna(False).astype(float)
        mask = (pd.to_datetime(df["date"]) >= first_oos_date) & event.notna()
        max_abs_corr = 0.0
        max_corr_name = ""
        max_corr_type = ""
        max_overlap = 0.0
        max_overlap_name = ""
        for col in comp_cols:
            x = pd.to_numeric(df[col], errors="coerce")
            aligned = pd.concat([event.loc[mask], x.loc[mask]], axis=1).dropna()
            if len(aligned) < 200 or aligned.iloc[:, 1].nunique() < 2:
                continue
            c = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
            comp_type = classify_family(col)
            abs_c = abs(c) if np.isfinite(c) else np.nan
            red_rows.append(
                {
                    "rule_name": rule["rule_name"],
                    "target": rule["target"],
                    "comparison_name": col,
                    "comparison_type": comp_type,
                    "correlation": c,
                    "abs_correlation": abs_c,
                }
            )
            if np.isfinite(abs_c) and abs_c > max_abs_corr:
                max_abs_corr = abs_c
                max_corr_name = col
                max_corr_type = comp_type
            unique = set(aligned.iloc[:, 1].dropna().unique())
            if unique.issubset({0, 1, 0.0, 1.0, False, True}):
                a = aligned.iloc[:, 0] > 0
                b = aligned.iloc[:, 1] > 0
                inter = int((a & b).sum())
                union = int((a | b).sum())
                overlap = inter / union if union else np.nan
                overlap_rows.append(
                    {
                        "rule_name": rule["rule_name"],
                        "target": rule["target"],
                        "comparison_name": col,
                        "comparison_type": comp_type,
                        "jaccard_overlap": overlap,
                        "event_count": int(a.sum()),
                        "comparison_event_count": int(b.sum()),
                    }
                )
                if np.isfinite(overlap) and overlap > max_overlap:
                    max_overlap = overlap
                    max_overlap_name = col

        p = perf[(perf["rule_name"] == rule["rule_name"]) & (perf["target"] == rule["target"])]
        p = p.iloc[0] if not p.empty else pd.Series(dtype=object)
        st = stability[stability["rule_name"] == rule["rule_name"]]
        positive_period_share = float((st["return_lift"] > 0).mean()) if not st.empty else np.nan
        event_frequency = p.get("event_frequency", np.nan)
        n_events = p.get("n_events", 0)
        return_lift = p.get("return_lift", np.nan)
        precision_lift = p.get("precision_lift", np.nan)
        if max_overlap >= 0.70 and "state_lag1" in max_overlap_name:
            flag = "MOSTLY_DUPLICATES_STATE_ENGINE"
        elif max_overlap >= 0.70 or max_abs_corr >= 0.70:
            flag = "MOSTLY_DUPLICATES_EXISTING_SIGNAL"
        elif max_corr_type in {"known_proxy_context", "ppp_latent_factor_context"} and max_abs_corr >= 0.55:
            flag = "PROXY_DISGUISE"
        elif event_frequency < 0.025 or n_events < 80:
            flag = "INSUFFICIENT_EVIDENCE"
        elif event_frequency > 0.65:
            flag = "TOO_COMPLEX_TO_TRADE"
        elif np.isfinite(return_lift) and return_lift > 0 and np.isfinite(precision_lift) and precision_lift > 0 and positive_period_share >= 0.5:
            flag = "INCREMENTAL_NEW_SIGNAL"
        else:
            flag = "INSUFFICIENT_EVIDENCE"
        inc_rows.append(
            {
                "rule_name": rule["rule_name"],
                "target": rule["target"],
                "incrementality_flag": flag,
                "max_abs_correlation": max_abs_corr,
                "max_corr_comparison": max_corr_name,
                "max_corr_comparison_type": max_corr_type,
                "max_event_overlap": max_overlap,
                "max_overlap_comparison": max_overlap_name,
                "event_frequency": event_frequency,
                "n_events": n_events,
                "return_lift": return_lift,
                "precision_lift": precision_lift,
                "positive_subperiod_return_lift_share": positive_period_share,
                "tradeable_actionable": flag in {"INCREMENTAL_NEW_SIGNAL", "INSUFFICIENT_EVIDENCE"} and event_frequency <= 0.65,
            }
        )
    red = pd.DataFrame(red_rows).sort_values(["rule_name", "abs_correlation"], ascending=[True, False])
    overlap = pd.DataFrame(overlap_rows).sort_values(["rule_name", "jaccard_overlap"], ascending=[True, False]) if overlap_rows else pd.DataFrame()
    inc = pd.DataFrame(inc_rows)
    save_csv(red, OUT / "qqq_redundancy_summary.csv")
    save_csv(inc, OUT / "qqq_incrementality_summary.csv")
    save_csv(overlap, OUT / "qqq_rule_event_overlap.csv")
    return red, inc, overlap


def shortlist_candidates(rules: pd.DataFrame, perf: pd.DataFrame, inc: pd.DataFrame, state_rules: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if rules.empty:
        empty = pd.DataFrame()
        save_csv(empty, OUT / "qqq_candidate_interaction_signal_shortlist.csv")
        save_csv(empty, OUT / "qqq_rejected_interaction_log.csv")
        save_csv(empty, OUT / "qqq_next_phase_queue.csv")
        return empty, empty, empty
    merged = rules.merge(perf, on=["rule_name", "target"], how="left", suffixes=("", "_perf")).merge(inc, on=["rule_name", "target"], how="left", suffixes=("", "_inc"))
    state_best = pd.DataFrame()
    if not state_rules.empty:
        state_best = (
            state_rules.assign(abs_precision_lift=state_rules["precision_lift"].abs())
            .sort_values(["rule_name", "abs_precision_lift"], ascending=[True, False])
            .groupby("rule_name")
            .head(1)[["rule_name", "market_state", "precision_lift", "event_frequency"]]
            .rename(columns={"market_state": "best_state", "precision_lift": "best_state_precision_lift", "event_frequency": "best_state_event_frequency"})
        )
        merged = merged.merge(state_best, on="rule_name", how="left")
    classifications = []
    reject_reasons = []
    next_phases = []
    for _, r in merged.iterrows():
        n_events = r.get("n_events", 0)
        freq = r.get("event_frequency", np.nan)
        ret_lift = r.get("return_lift", np.nan)
        prec_lift = r.get("precision_lift", np.nan)
        stability = r.get("stability", np.nan)
        inc_flag = r.get("incrementality_flag", "")
        importance = r.get("mean_abs_model_importance", np.nan)
        state_lift = r.get("best_state_precision_lift", np.nan)
        high = (
            inc_flag == "INCREMENTAL_NEW_SIGNAL"
            and n_events >= 120
            and 0.04 <= freq <= 0.45
            and np.isfinite(ret_lift)
            and ret_lift > 0.0010
            and np.isfinite(prec_lift)
            and prec_lift > 0.025
            and np.isfinite(stability)
            and stability >= 0.55
            and (not np.isfinite(importance) or importance > 0)
        )
        if high:
            cls = "HIGH_PRIORITY_SIGNAL_TEST"
            reason = "stable OOS lift, interpretable, enough coverage, and not redundant by QQQ screens"
            phase = "QQQ2 explicit interaction-signal validation"
        elif inc_flag == "INCREMENTAL_NEW_SIGNAL" and np.isfinite(state_lift) and state_lift > 0.05 and n_events >= 60:
            cls = "PROMISING_STATE_SPECIFIC_SIGNAL"
            reason = "interaction is strongest in a specific state and needs state-specific validation"
            phase = "QQQ2 state-specific interaction validation"
        elif inc_flag == "INCREMENTAL_NEW_SIGNAL" and n_events >= 80 and np.isfinite(ret_lift) and ret_lift > 0:
            cls = "NEEDS_TRIPLE_BARRIER_VALIDATION"
            reason = "positive event-return lift but stability/coverage gates are not high-priority clean"
            phase = "QQQ2 or OOO5-style triple-barrier validation"
        elif inc_flag in {"MOSTLY_DUPLICATES_EXISTING_SIGNAL", "MOSTLY_DUPLICATES_STATE_ENGINE", "PROXY_DISGUISE"}:
            cls = "REDUNDANT_OR_DUPLICATIVE"
            reason = inc_flag
            phase = "none"
        elif inc_flag == "TOO_COMPLEX_TO_TRADE":
            cls = "TOO_COMPLEX"
            reason = "too broad or hard to turn into a clean signal"
            phase = "none"
        elif np.isfinite(freq) and freq > 0.45 and np.isfinite(ret_lift) and ret_lift > 0:
            cls = "NEEDS_VOL_MANAGED_SIZING"
            reason = "broad event with some lift, needs selectivity/sizing if pursued"
            phase = "OOO3-style volatility/selectivity sizing"
        else:
            cls = "REJECT"
            reason = "insufficient stable incremental evidence"
            phase = "none"
        classifications.append(cls)
        reject_reasons.append(reason)
        next_phases.append(phase)
    merged["classification"] = classifications
    merged["reason"] = reject_reasons
    merged["next_recommended_phase"] = next_phases
    shortlist = merged[merged["classification"].isin(["HIGH_PRIORITY_SIGNAL_TEST", "PROMISING_STATE_SPECIFIC_SIGNAL", "NEEDS_TRIPLE_BARRIER_VALIDATION", "NEEDS_VOL_MANAGED_SIZING"])].copy()
    reject = merged[~merged.index.isin(shortlist.index)].copy()
    queue = shortlist.sort_values(["classification", "return_lift", "precision_lift"], ascending=[True, False, False])
    save_csv(shortlist, OUT / "qqq_candidate_interaction_signal_shortlist.csv")
    save_csv(reject, OUT / "qqq_rejected_interaction_log.csv")
    save_csv(queue, OUT / "qqq_next_phase_queue.csv")
    return shortlist, reject, queue


def decide_next_action(shortlist: pd.DataFrame, inc: pd.DataFrame, state_perf: pd.DataFrame) -> pd.DataFrame:
    high = shortlist[shortlist["classification"] == "HIGH_PRIORITY_SIGNAL_TEST"] if not shortlist.empty else pd.DataFrame()
    state_sig = shortlist[shortlist["classification"] == "PROMISING_STATE_SPECIFIC_SIGNAL"] if not shortlist.empty else pd.DataFrame()
    needs_tb = shortlist[shortlist["classification"] == "NEEDS_TRIPLE_BARRIER_VALIDATION"] if not shortlist.empty else pd.DataFrame()
    mostly_state = False
    if not inc.empty:
        mostly_state = (inc["incrementality_flag"] == "MOSTLY_DUPLICATES_STATE_ENGINE").mean() >= 0.35
    if not high.empty:
        rec = "PROCEED_TO_QQQ2_INTERACTION_SIGNAL_VALIDATION"
        reason = "At least one interaction signal cleared high-priority OOS, stability, interpretability, coverage, and incrementality gates."
    elif not state_sig.empty or mostly_state:
        rec = "PROCEED_TO_SSS_REGIME_SEQUENCE_MODELING"
        reason = "Interaction value appears state-specific or state-engine-like rather than a clean broad ETF signal."
    elif not needs_tb.empty:
        rec = "PROCEED_TO_QQQ2_INTERACTION_SIGNAL_VALIDATION"
        reason = "No high-priority signal yet, but some interaction rules have enough positive OOS lift to justify explicit validation before rejection."
    elif not state_perf.empty and state_perf["spearman_ic"].fillna(0).max() > 0.06:
        rec = "PROCEED_TO_RRR_SLEEVE_META_LABELING"
        reason = "ETF-level interactions are not clean enough, but state/model dispersion suggests timing may be more useful at sleeve/component level."
    else:
        rec = "STOP_HARD_ML_FOR_NOW"
        reason = "Interactions are unstable, redundant, or not actionable under QQQ gates."
    out = pd.DataFrame(
        [
            {
                "recommendation": rec,
                "reason": reason,
                "high_priority_signal_count": int(len(high)),
                "promising_state_specific_count": int(len(state_sig)),
                "needs_triple_barrier_count": int(len(needs_tb)),
                "shortlist_count": int(len(shortlist)),
            }
        ]
    )
    save_csv(out, OUT / "qqq_next_action_recommendation.csv")
    return out


def write_report(
    dataset: pd.DataFrame,
    target_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    splits: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    model_metrics: pd.DataFrame,
    family_importance: pd.DataFrame,
    interaction_importance: pd.DataFrame,
    rules: pd.DataFrame,
    state_rules: pd.DataFrame,
    inc: pd.DataFrame,
    shortlist: pd.DataFrame,
    rejected: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    dataset_summary = pd.DataFrame(
        [
            {"item": "rows", "value": dataset.shape[0]},
            {"item": "columns", "value": dataset.shape[1]},
            {"item": "tickers", "value": dataset["ticker"].nunique()},
            {"item": "start_date", "value": dataset["date"].min().date()},
            {"item": "end_date", "value": dataset["date"].max().date()},
        ]
    )
    files = [
        "scripts/phase_qqq_deep_feature_interaction_mining.py",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset_sample.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_dataset_schema.json",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_manifest.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_target_summary.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_data_quality_report.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_leakage_checklist.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_walkforward_splits.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_baseline_model_metrics.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_metrics.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_predictions.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_calibration_summary.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_importance.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_feature_family_importance.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_interaction_importance.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_state_specific_model_performance.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_subperiod_stability.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_extracted_interaction_rules.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_performance_summary.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_state_specific_rules.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_stability.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_redundancy_summary.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_incrementality_summary.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_rule_event_overlap.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_candidate_interaction_signal_shortlist.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_rejected_interaction_log.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_next_phase_queue.csv",
        "data/research/phase_qqq_deep_feature_interaction_mining/qqq_next_action_recommendation.csv",
        "docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md",
        "docs/research/project_journey.md",
    ]
    best_metrics = model_metrics.sort_values(["target", "spearman_ic"], ascending=[True, False]).groupby("target").head(4) if not model_metrics.empty else model_metrics
    top_family = family_importance.groupby("feature_family").agg(mean_abs_importance=("mean_abs_importance", "mean"), feature_count=("feature_count", "sum")).reset_index().sort_values("mean_abs_importance", ascending=False) if not family_importance.empty else family_importance
    top_interactions = interaction_importance[interaction_importance.get("interaction_source", "") == "explicit_interaction_feature"].head(20) if not interaction_importance.empty else interaction_importance
    top_inc = inc.sort_values(["incrementality_flag", "return_lift"], ascending=[True, False]).head(20) if not inc.empty else inc
    next_rec = next_action.iloc[0]["recommendation"] if not next_action.empty else "UNKNOWN"
    next_reason = next_action.iloc[0]["reason"] if not next_action.empty else ""
    next_prompt = (
        "Implement the next recommended phase using QQQ outputs. If QQQ2, convert only shortlisted interaction rules into explicit "
        "candidate Layer 1 signals, validate IC decay, state behavior, event overlap, triple-barrier outcomes, and redundancy before any "
        "portfolio pass-through. Keep production/shadow/GGG1 unchanged."
    )
    report = f"""# Phase QQQ -- Deep Feature Interaction Mining

Date: 2026-04-27

## Commands Executed
{chr(10).join(f"- `{cmd}`" for cmd in COMMANDS)}

## Files Created / Modified
{chr(10).join(f"- `{f}`" for f in files)}

## Dataset Construction Summary
{markdown_table(dataset_summary)}

The QQQ dataset uses PPP lagged ETF features as the main source, adds lagged
known proxy returns and lagged PPP factor returns, creates lagged state dummies,
and builds explicit economically constrained interactions. Current
`market_state` is retained for validation grouping only.

## Leakage Checks
{markdown_table(leakage, n=20)}

## Target Definitions and Class Balance
{markdown_table(target_summary.head(16), n=16)}

## Walk-Forward Validation Design
Initial train dates: `{INITIAL_TRAIN_DATES}`. Refit frequency: `{REFIT_FREQ}` weekly dates.
Splits generated: `{len(splits)}`.

{markdown_table(splits.head(8), n=8)}

## Baseline Model Results
{markdown_table(baseline_metrics.sort_values(["target", "spearman_ic"], ascending=[True, False]).head(16) if not baseline_metrics.empty else baseline_metrics, n=16)}

## Nonlinear Model Results
{markdown_table(best_metrics, n=20)}

## Feature Family Importance
{markdown_table(top_family, n=16)}

## Interaction and Rule Findings
Top explicit interaction importances:

{markdown_table(top_interactions, n=20)}

Extracted rule examples:

{markdown_table(rules.sort_values("oos_metric_lift", ascending=False).head(16) if not rules.empty else rules, n=16)}

## State-Specific Interactions
{markdown_table(state_rules.sort_values("precision_lift", ascending=False).head(16) if not state_rules.empty else state_rules, n=16)}

## Redundancy and Incrementality
{markdown_table(top_inc, n=20)}

## Candidate Interaction Signal Shortlist
{markdown_table(shortlist.sort_values("return_lift", ascending=False).head(20) if not shortlist.empty else shortlist, n=20)}

## Rejected Interactions and Why
{markdown_table(rejected[["rule_name", "target", "classification", "reason", "return_lift", "precision_lift", "event_frequency"]].head(20) if not rejected.empty else rejected, n=20)}

## Final Recommendation
**{next_rec}**

Reason: {next_reason}

## Exact Prompt Outline for Next Phase
{next_prompt}

## Resume-Worthy Technical Summary
QQQ built four ETF cross-sectional top-quartile targets from the PPP panel:
4w/8w forward return and 4w/8w risk-adjusted forward return. It used fixed
expanding-window splits with no random shuffling, evaluated naive/state/momentum
baselines, L2 logistic models, shallow decision trees, controlled random
forests, and shallow histogram gradient boosting. It generated economically
motivated explicit interactions such as momentum x volatility, credit strength
x trend, breadth x momentum, real-asset strength x stress, quality/BAB/carry x
volatility, OOO lead-lag x state/trend, and PPP factor context x ETF
characteristics. QQQ extracted rule events, checked subperiod and state
behavior, compared rules against existing Layer 1/OOO/PPP/state/proxy context,
and wrote a shortlist without creating portfolio candidates or changing any
production/shadow/GGG1 logic.
"""
    DOC.write_text(report)


def update_journey(next_action: pd.DataFrame) -> None:
    rec = next_action.iloc[0]["recommendation"] if not next_action.empty else "UNKNOWN"
    reason = next_action.iloc[0]["reason"] if not next_action.empty else ""
    section = f"""
## Section 89 -- Phase QQQ Deep Feature Interaction Mining

Date: 2026-04-27. Phase QQQ was diagnostic-only. It used the PPP lagged
ETF-characteristic panel, OOO signal lineage, Layer 1 features, lagged state
context, known proxy context, and PPP factor context to test controlled
nonlinear empirical-asset-pricing style feature interactions with expanding
walk-forward validation. It created no portfolio candidates and did not change
production, shadow, GGG1 logic, or live trading behavior.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text() if JOURNEY.exists() else ""
    marker = "## Section 89 -- Phase QQQ Deep Feature Interaction Mining"
    if marker in text:
        text = text[: text.index(marker)].rstrip() + "\n\n" + section.strip() + "\n"
    else:
        text = text.rstrip() + "\n\n" + section.strip() + "\n"
    JOURNEY.write_text(text)


def main() -> None:
    ensure_dirs()
    dataset, feature_manifest, target_summary, specs, base_features, interaction_features = build_dataset()
    splits = build_walkforward_splits(dataset)
    predictions, importance, tree_pairs = run_walkforward_models(dataset, splits, base_features, interaction_features)
    model_metrics, baseline_metrics, calibration, state_perf, subperiod = evaluate_predictions(predictions)
    family_importance, interaction_importance = aggregate_importance(importance, tree_pairs)
    rules, rule_perf, state_rules, rule_stability = rule_discovery(dataset, specs, interaction_importance, splits)
    redundancy, incrementality, overlap = redundancy_and_incrementality(dataset, specs, rules, rule_perf, rule_stability)
    shortlist, rejected, queue = shortlist_candidates(rules, rule_perf, incrementality, state_rules)
    next_action = decide_next_action(shortlist, incrementality, state_perf)
    leakage = pd.read_csv(OUT / "qqq_leakage_checklist.csv")
    write_report(
        dataset,
        target_summary,
        leakage,
        splits,
        baseline_metrics,
        model_metrics,
        family_importance,
        interaction_importance,
        rules,
        state_rules,
        incrementality,
        shortlist,
        rejected,
        next_action,
    )
    update_journey(next_action)
    print("Phase QQQ deep feature interaction mining complete.")
    print(f"Outputs: {OUT}")
    print(f"Report: {DOC}")
    print(f"Recommendation: {next_action.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
