#!/usr/bin/env python3
"""Measure whether year-over-year 10-K language change predicts returns.

Item S1, source-blocked since Step 202 and acquired in Step 252. The hypothesis
and its sign were declared in `config/filing_language_change_registry_v1.json`
before this ran: Cohen, Malloy and Nguyen find that filings which change MORE
predict LOWER returns, so the tradeable signal is similarity and a reversed sign
is a failed replication rather than a discovery.

Two things get controlled that would otherwise decide the answer quietly.

Similarity correlates mechanically with document length -- a filing that grew by
half is dissimilar to last year's whatever the words say -- so the information
coefficient is measured again after the change in word count is regressed out. If
the signal only survives before that, it is document length wearing a costume.

And filings arrive all year, so a weekly cross-section would compare a January
filer against a filing eleven months stale. Cohorts here are calendar quarters of
the filing date, which keeps every comparison between filings published close
together.

No strategy is built and nothing can be promoted from this.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/filing_language_change_registry_v1.json"
PARSED = ROOT / "data/sec_filing_text_v1/parsed"

NUMERIC = set("0123456789")


def tokens(text: str) -> list[str]:
    """Words only. Numbers are dropped here, having been kept through parsing so
    the section headings could be found at all."""
    return [w for w in text.split() if w and not (set(w) <= NUMERIC) and len(w) > 2]


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return float("nan")
    common = set(a) & set(b)
    numerator = sum(a[w] * b[w] for w in common)
    denominator = np.sqrt(sum(v * v for v in a.values())) * np.sqrt(sum(v * v for v in b.values()))
    return float(numerator / denominator) if denominator else float("nan")


def jaccard(a: Counter, b: Counter) -> float:
    if not a or not b:
        return float("nan")
    sa, sb = set(a), set(b)
    union = len(sa | sb)
    return float(len(sa & sb) / union) if union else float("nan")


def load(accession: str) -> dict | None:
    path = PARSED / f"{accession}.json.gz"
    if not path.is_file():
        return None
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def forward_returns(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    forward = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(horizon).sum() >= horizon
    return forward.where(valid).shift(-horizon)


def residualise(signal: np.ndarray, control: np.ndarray) -> np.ndarray:
    """Return the part of the signal that the control does not explain."""
    mask = np.isfinite(signal) & np.isfinite(control)
    if mask.sum() < 10:
        return np.full_like(signal, np.nan)
    x = np.column_stack([np.ones(mask.sum()), control[mask]])
    beta, *_ = np.linalg.lstsq(x, signal[mask], rcond=None)
    out = np.full_like(signal, np.nan)
    out[mask] = signal[mask] - x @ beta
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/filing_language_change_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    declared = registry["declared_configurations"]
    threshold = float(registry["bonferroni_threshold"])

    index = [json.loads(line) for line in
             (PARSED / "parsed_index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    frame = pd.DataFrame(index)
    frame["filing_date"] = pd.to_datetime(frame.filing_date)
    pairs = frame[frame.prior_accession.notna()].copy()

    prices = pd.read_csv(ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz",
                         index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]

    rows = []
    for record in pairs.itertuples(index=False):
        current = load(record.accession)
        prior = load(record.prior_accession)
        if current is None or prior is None:
            continue
        entry = {"cik10": str(record.cik10), "accession": record.accession,
                 "filing_date": record.filing_date}
        for section in ("full", "item_7", "item_1a"):
            a, b = Counter(tokens(current.get(section, ""))), Counter(tokens(prior.get(section, "")))
            entry[f"cosine__{section}"] = cosine(a, b)
            entry[f"jaccard__{section}"] = jaccard(a, b)
            entry[f"length_change__{section}"] = (
                float(sum(a.values()) / sum(b.values()) - 1.0) if sum(b.values()) else np.nan)
        rows.append(entry)
    similarity = pd.DataFrame(rows)
    if similarity.empty:
        raise SystemExit("no comparable filing pairs were parsed")
    similarity["cohort"] = similarity.filing_date.dt.to_period("Q").astype(str)

    index_dates = prices.index
    results = []
    per_config_ic = {}
    for measure in declared["similarity_measures"]:
        column_prefix = "cosine" if measure.startswith("cosine") else "jaccard"
        for section in declared["sections"]:
            column = f"{column_prefix}__{section}"
            for horizon in declared["forward_horizon_weeks"]:
                forward = forward_returns(prices, horizon)
                raw_ic, controlled_ic, sizes = [], [], []
                for cohort, block in similarity.groupby("cohort"):
                    values, controls, outcomes = [], [], []
                    for row in block.itertuples(index=False):
                        cik = row.cik10
                        if cik not in prices.columns:
                            continue
                        later = index_dates[index_dates > row.filing_date]
                        if not len(later):
                            continue
                        week = later[0]
                        if week not in forward.index:
                            continue
                        outcome = forward.at[week, cik]
                        value = getattr(row, column.replace("__", "_") if False else column, np.nan)
                        value = row._asdict()[column] if hasattr(row, "_asdict") else value
                        control = row._asdict()[f"length_change__{section}"]
                        if not np.isfinite(value) or not np.isfinite(outcome):
                            continue
                        values.append(value); outcomes.append(outcome); controls.append(control)
                    if len(values) < 50:
                        continue
                    v, o, c = np.array(values), np.array(outcomes), np.array(controls)
                    raw_ic.append(float(pd.Series(v).rank().corr(pd.Series(o).rank())))
                    residual = residualise(v, c)
                    if np.isfinite(residual).sum() >= 50:
                        controlled_ic.append(float(pd.Series(residual).rank().corr(pd.Series(o).rank())))
                    sizes.append(len(values))
                if len(raw_ic) < 8:
                    continue
                raw = np.array(raw_ic); controlled = np.array(controlled_ic)
                per_config_ic[f"{measure}|{section}|{horizon}w"] = raw.tolist()
                results.append({
                    "measure": measure, "section": section, "forward_horizon_weeks": horizon,
                    "cohorts": len(raw), "median_cohort_size": float(np.median(sizes)),
                    "mean_ic": float(raw.mean()),
                    "t_stat": float(raw.mean() / (raw.std(ddof=1) / np.sqrt(len(raw)))),
                    "share_positive": float((raw > 0).mean()),
                    "mean_ic_length_controlled": float(controlled.mean()) if len(controlled) else None,
                    "t_stat_length_controlled": (
                        float(controlled.mean() / (controlled.std(ddof=1) / np.sqrt(len(controlled))))
                        if len(controlled) > 1 else None),
                })
    table = pd.DataFrame(results)
    if not table.empty:
        from scipy import stats
        table["p_value"] = [float(stats.ttest_1samp(per_config_ic[
            f"{r.measure}|{r.section}|{r.forward_horizon_weeks}w"], 0.0).pvalue) for r in table.itertuples()]
        table["clears_bonferroni"] = table.p_value < threshold

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    similarity.to_csv(out / "similarity.csv", index=False)
    table.to_csv(out / "information_coefficients.csv", index=False)

    clearing = table[table.clears_bonferroni] if not table.empty else table
    positive = clearing[clearing.mean_ic > 0] if not clearing.empty else clearing
    survives_length = (positive[positive.t_stat_length_controlled.abs() > 2.0]
                       if not positive.empty else positive)
    if table.empty:
        verdict = "no configuration produced enough cohorts to measure"
    elif clearing.empty:
        verdict = ("no configuration clears Bonferroni: 10-K language change does not predict "
                   "returns on this universe. S1 closes as a negative result.")
    elif positive.empty:
        verdict = ("configurations clear but with the sign OPPOSITE to the literature; recorded as a "
                   "failed replication, not a discovery")
    elif survives_length.empty:
        verdict = "clears only before the length control: the signal is document length wearing a costume"
    else:
        verdict = ("clears with the declared sign and survives the length control; correlation against "
                   "existing strategies is the remaining question")

    result = {
        "experiment": "filing_language_change_v1",
        "declared_trials": declared["total_trials"], "bonferroni_threshold": threshold,
        "filing_pairs_compared": int(len(similarity)),
        "issuers": int(similarity.cik10.nunique()),
        "window": [str(similarity.filing_date.min().date()), str(similarity.filing_date.max().date())],
        "median_cosine_full": float(similarity["cosine__full"].median()),
        "median_jaccard_full": float(similarity["jaccard__full"].median()),
        "configurations_clearing": int(len(clearing)),
        "configurations_clearing_with_declared_sign": int(len(positive)),
        "verdict": verdict,
        "cumulative_trial_warning": registry["cumulative_trial_warning"],
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"filing pairs {result['filing_pairs_compared']:,} across {result['issuers']} issuers, "
          f"{result['window'][0]} to {result['window'][1]}")
    print(f"median cosine similarity (full document): {result['median_cosine_full']:.4f}\n")
    if not table.empty:
        print(table[["measure", "section", "forward_horizon_weeks", "cohorts", "median_cohort_size",
                     "mean_ic", "t_stat", "mean_ic_length_controlled", "t_stat_length_controlled",
                     "p_value", "clears_bonferroni"]].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
