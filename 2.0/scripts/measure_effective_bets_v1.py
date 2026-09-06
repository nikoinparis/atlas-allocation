#!/usr/bin/env python3
"""Measure how many independent bets each forward book actually makes.

The method is an independent reimplementation of the owner's own study,
github.com/nikoinparis/effective-number-of-bets, from the formulas stated in its
README and report rather than from its package, so agreement here is a check on
that result rather than a restatement of it. Three quantities:

  participation ratio   (sum L)^2 / sum L^2 over correlation eigenvalues; how many
                        independent risk sources the universe contains at all
  independence null     E[PR] ~ N(T-1)/(T+N-2); what a sample correlation matrix
                        would report if every asset really were independent, which
                        is the only fair comparison -- never compare against N
  PCA effective bets    rotate into principal components, attribute portfolio
                        variance across them, take exp of the entropy of the shares

and, because that last number is meaningless without it, the signal variance
share: the fraction of portfolio variance sitting in components above the
Marchenko-Pastur noise edge. The study's Finding 5.2 is that a shrinkage
minimum-variance portfolio reported 11.93 effective bets with 95.6% of its
variance below that edge, and collapsed to 1.59 once denoised. Any effective-bet
count quoted here without its signal share is not a measurement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
OUTPUT = ROOT / "evidence/effective_bets_forward_books_v1"
CASH = "cash::USD"
SEED = 20260904
BOOTSTRAP_DRAWS = 2000
BLOCK_WEEKS = 13


def participation_ratio(correlation: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(correlation)
    eigenvalues = eigenvalues[eigenvalues > 0]
    return float(eigenvalues.sum() ** 2 / (eigenvalues ** 2).sum())


def independence_null(n_assets: int, n_observations: int) -> float:
    return n_assets * (n_observations - 1) / (n_observations + n_assets - 2)


def marchenko_pastur_edge(n_assets: int, n_observations: int) -> float:
    return (1.0 + np.sqrt(n_assets / n_observations)) ** 2


def entropy_effective_number(shares: np.ndarray) -> float:
    shares = shares[shares > 1e-15]
    return float(np.exp(-(shares * np.log(shares)).sum()))


def principal_component_bets(covariance: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    keep = eigenvalues > 1e-18
    eigenvalues, eigenvectors = eigenvalues[keep], eigenvectors[:, keep]
    exposures = np.sqrt(eigenvalues) * (eigenvectors.T @ weights)
    variance = float((exposures ** 2).sum())
    shares = exposures ** 2 / variance if variance > 0 else exposures ** 2
    return {"effective_bets": entropy_effective_number(shares), "variance": variance,
            "shares": shares, "eigenvalues": eigenvalues}


def minimum_torsion_bets(returns: pd.DataFrame, weights: np.ndarray) -> float:
    """Symmetric-orthogonalisation basis: the uncorrelated factors closest to the assets."""
    correlation = np.corrcoef(returns.to_numpy().T)
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    root = eigenvectors @ np.diag(np.sqrt(np.clip(eigenvalues, 0, None))) @ eigenvectors.T
    exposures = root @ (weights * returns.std(ddof=1).to_numpy())
    total = float((exposures ** 2).sum())
    return entropy_effective_number(exposures ** 2 / total) if total > 0 else 0.0


def signal_variance_share(returns: pd.DataFrame, weights: np.ndarray) -> dict[str, float]:
    """Share of portfolio variance above the Marchenko-Pastur noise edge."""
    observations, assets = returns.shape
    correlation = np.corrcoef(returns.to_numpy().T)
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    volatility = returns.std(ddof=1).to_numpy()
    scaled = weights * volatility
    exposures = np.sqrt(np.clip(eigenvalues, 0, None)) * (eigenvectors.T @ scaled)
    total = float((exposures ** 2).sum())
    edge = marchenko_pastur_edge(assets, observations)
    above = float((exposures[eigenvalues > edge] ** 2).sum())
    signal = exposures[eigenvalues > edge] ** 2
    denoised = entropy_effective_number(signal / signal.sum()) if signal.sum() > 0 else 0.0
    return {"signal_variance_share": above / total if total > 0 else 0.0,
            "mp_edge": edge, "eigenvalues_above_edge": int((eigenvalues > edge).sum()),
            "effective_bets_signal_only": denoised}


def measure(returns: pd.DataFrame, weights: pd.Series, label: str) -> dict[str, object]:
    aligned = weights.reindex(returns.columns).fillna(0.0).to_numpy()
    covariance = np.cov(returns.to_numpy().T, ddof=1)
    pca = principal_component_bets(covariance, aligned)
    signal = signal_variance_share(returns, aligned)
    return {
        "book": label,
        "names_held": int((np.abs(aligned) > 1e-12).sum()),
        "effective_bets_pca_all_components": round(pca["effective_bets"], 3),
        "effective_bets_signal_only": round(signal["effective_bets_signal_only"], 3),
        "effective_bets_minimum_torsion": round(minimum_torsion_bets(returns, aligned), 3),
        "signal_variance_share": round(signal["signal_variance_share"], 4),
        "interpretable": bool(signal["signal_variance_share"] >= 0.5),
        "eigenvalues_above_mp_edge": signal["eigenvalues_above_edge"],
        "annualised_volatility": round(float(np.sqrt(pca["variance"] * 52)), 4),
    }


def block_bootstrap_pr(returns: pd.DataFrame, draws: int, block: int) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    values, observations = returns.to_numpy(), len(returns)
    blocks = max(1, observations // block)
    out = []
    for _ in range(draws):
        starts = rng.integers(0, observations - block + 1, size=blocks)
        sample = np.concatenate([values[s:s + block] for s in starts])
        out.append(participation_ratio(np.corrcoef(sample.T)))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def load_books() -> dict[str, pd.Series]:
    books: dict[str, pd.Series] = {}
    for pid, path, kind in [
        ("covariance_minimum_variance_v1", "evidence/forward_covariance_minimum_variance_v1/decisions.jsonl", "jsonl"),
        ("breadth_confirmed_trend_return_ceiling_v3", "evidence/forward_breadth_confirmed_trend_return_ceiling_v3/decisions.jsonl", "jsonl"),
        ("past_only_consensus_selector_return_v1", "evidence/forward_past_only_consensus_selector_return_v1/decisions.jsonl", "jsonl"),
        ("return_first_60_40_blend_v1", "evidence/forward_return_first_60_40_blend_v1/decisions.jsonl", "jsonl"),
    ]:
        records = [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line.strip()]
        weights = pd.Series(records[-1]["target_weights"], dtype=float).drop(index=CASH, errors="ignore")
        books[pid] = weights / weights.sum()
    return books


def main() -> int:
    prices = pd.read_csv(PANEL, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    returns_all = prices.pct_change().dropna(how="all")

    universes = {
        "longest_history": returns_all.dropna(axis=1, how="any"),
        "complete_case_2014_on": returns_all.loc["2014-11-01":].dropna(axis=1, how="any"),
    }

    universe_rows = []
    for label, frame in universes.items():
        frame = frame.dropna()
        observations, assets = frame.shape
        pr = participation_ratio(np.corrcoef(frame.to_numpy().T))
        low, high = block_bootstrap_pr(frame, BOOTSTRAP_DRAWS, BLOCK_WEEKS)
        universe_rows.append({
            "universe": label, "assets": assets, "weeks": observations,
            "participation_ratio": round(pr, 3),
            "ci95": [round(low, 3), round(high, 3)],
            "independence_null": round(independence_null(assets, observations), 2),
            "overstatement_vs_counting_assets": round(assets / pr, 2),
        })

    panel = universes["complete_case_2014_on"].dropna()
    books = load_books()
    books["equal_weight_35_reference"] = pd.Series(1.0 / len(panel.columns), index=panel.columns)
    book_rows = [measure(panel, weights, label) for label, weights in books.items()]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": "effective_bets_forward_books_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method_source": "independent reimplementation of github.com/nikoinparis/effective-number-of-bets",
        "panel": str(PANEL.relative_to(ROOT)),
        "panel_data_through": str(panel.index[-1].date()),
        "universe_breadth": universe_rows,
        "books": book_rows,
        "note": ("effective-bet counts are only interpretable where signal_variance_share is at or "
                 "above 0.5; below that the count describes noise directions, which is the study's "
                 "Finding 5.2"),
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print("universe breadth")
    for row in universe_rows:
        print(f"  {row['universe']:<24}{row['assets']:>3} assets {row['weeks']:>5} weeks   "
              f"PR {row['participation_ratio']:>6.2f} {str(row['ci95']):<16} "
              f"null {row['independence_null']:>6.2f}   overstatement {row['overstatement_vs_counting_assets']:>5.1f}x")
    print(f"\nforward books, measured on {panel.shape[1]} assets x {panel.shape[0]} weeks")
    print(f"  {'book':<44}{'names':>6}{'all PCs':>9}{'signal':>9}{'min-tors':>10}{'sig share':>11}")
    for row in book_rows:
        print(f"  {row['book']:<44}{row['names_held']:>6}{row['effective_bets_pca_all_components']:>9.2f}"
              f"{row['effective_bets_signal_only']:>9.2f}{row['effective_bets_minimum_torsion']:>10.2f}"
              f"{row['signal_variance_share']:>11.2f}")
    print("\n  'all PCs' counts noise directions as bets and is the number Finding 5.1 says not to "
          "trust on a\n  concentrated book; 'signal' restricts the count to components above the "
          "Marchenko-Pastur edge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
