"""Run statistical validation audit across available research return files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from statistical_validation_layer import (
    ReturnFile,
    pbo_proxy,
    sanity_check_cv,
    strategy_validation_summary,
    validation_verdict,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PORT = DATA / "05_layer3_portfolio_construction"
RESEARCH = DATA / "research"
VALIDATION_OUT = RESEARCH / "validation"
DOCS = ROOT / "docs" / "research"
GGG = "improved_phaseggg_confirmed_only_robust_offense"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def md_table(df: pd.DataFrame, columns: Optional[List[str]] = None, n: int = 25) -> str:
    if df is None or df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view[[c for c in columns if c in view.columns]]
    view = view.head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    header = "| " + " | ".join(map(str, view.columns)) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def read_return_file(path: Path) -> Optional[ReturnFile]:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if df.empty:
        return None
    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    else:
        dates = pd.RangeIndex(len(df))
    candidate = path.stem
    for prefix in ["portfolio_version_returns_", "portfolio_returns_", "ggg_rebuild_", "rule_harness_", "c4_native_variant_"]:
        candidate = candidate.replace(prefix, "")

    return_col = None
    for col in ["net_return", "exact_net_return", "return", "portfolio_return", "strategy_return", "gross_return"]:
        if col in df.columns:
            return_col = col
            break
    if return_col is None:
        numeric_cols = [c for c in df.columns if c != "Date" and pd.api.types.is_numeric_dtype(pd.to_numeric(df[c], errors="coerce"))]
        if len(numeric_cols) == 1:
            return_col = numeric_cols[0]
    if return_col is None:
        return None
    returns = pd.to_numeric(df[return_col], errors="coerce")
    returns.index = dates
    turnover = None
    if "turnover" in df.columns:
        turnover = pd.to_numeric(df["turnover"], errors="coerce")
        turnover.index = dates
    if "variant" in df.columns and return_col in df.columns:
        # Long-form research returns. Split is handled by caller.
        return None
    return ReturnFile(candidate=candidate, source_file=rel(path), returns=returns, turnover=turnover)


def read_long_return_file(path: Path) -> List[ReturnFile]:
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    if df.empty or "variant" not in df.columns or "Date" not in df.columns:
        return []
    return_col = "net_return" if "net_return" in df.columns else "gross_return" if "gross_return" in df.columns else None
    if return_col is None:
        return []
    out = []
    for variant, group in df.groupby("variant"):
        dates = pd.to_datetime(group["Date"], errors="coerce").dt.tz_localize(None)
        returns = pd.to_numeric(group[return_col], errors="coerce")
        returns.index = dates
        turnover = None
        if "turnover" in group.columns:
            turnover = pd.to_numeric(group["turnover"], errors="coerce")
            turnover.index = dates
        out.append(ReturnFile(candidate=str(variant), source_file=f"{rel(path)}::{variant}", returns=returns, turnover=turnover))
    return out


def discover_return_files() -> List[ReturnFile]:
    files: List[ReturnFile] = []
    candidates = []
    candidates.extend(sorted(PORT.glob("portfolio_version_returns_*.csv")))
    candidates.extend(sorted(PORT.glob("portfolio_returns_*.csv")))
    candidates.extend(sorted(RESEARCH.glob("**/*returns*.csv")))
    candidates.extend(sorted(RESEARCH.glob("**/*variant_returns*.csv")))
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        long_rows = read_long_return_file(path)
        if long_rows:
            files.extend(long_rows)
            continue
        item = read_return_file(path)
        if item is not None and len(item.returns.dropna()) >= 20:
            files.append(item)
    # Keep the audit bounded but broad: production variants plus recent research
    # artifacts are enough to estimate trial-count pressure and validation status.
    unique: Dict[str, ReturnFile] = {}
    for item in files:
        key = f"{item.source_file}:{item.candidate}"
        unique[key] = item
    return list(unique.values())[:500]


def count_trials() -> Dict[str, int]:
    count = 0
    files = list(PORT.glob("*candidate_metrics*.csv")) + list(RESEARCH.glob("**/*metrics*.csv")) + list(RESEARCH.glob("**/*results*.csv"))
    for path in files:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        count += max(len(df), 1)
    return {"trial_count": max(count, 1), "trial_file_count": len(files)}


def load_benchmark(files: List[ReturnFile]) -> Optional[pd.Series]:
    for item in files:
        if GGG in item.candidate or GGG in item.source_file:
            return item.returns
    path = PORT / f"portfolio_version_returns_{GGG}.csv"
    item = read_return_file(path)
    return item.returns if item is not None else None


def audit_rows(files: List[ReturnFile], trial_count: int, benchmark: Optional[pd.Series]) -> pd.DataFrame:
    pbo_universe = {item.candidate: item.returns for item in files if len(item.returns.dropna()) >= 260}
    pbo = pbo_proxy(dict(list(pbo_universe.items())[:80]), n_splits=6)
    rows = []
    for item in files:
        summary = strategy_validation_summary(item.returns, benchmark_returns=benchmark, turnover=item.turnover, trial_count=trial_count)
        row = {
            "candidate": item.candidate,
            "source_file": item.source_file,
            **summary,
            "trial_count_warning": "high" if trial_count >= 100 else "moderate" if trial_count >= 25 else "low",
            "pbo_proxy": pbo.get("pbo_proxy", np.nan),
            "pbo_proxy_warning": "high" if pbo.get("pbo_proxy", np.nan) >= 0.50 else "moderate" if pbo.get("pbo_proxy", np.nan) >= 0.30 else "low",
        }
        row["validation_verdict"] = validation_verdict(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows)


def write_layer_doc() -> None:
    lines = [
        "# Statistical Validation Layer",
        "",
        "Research-only utilities inspired by Fama/EMH discipline and Lopez de Prado-style leakage and overfitting controls.",
        "",
        "## What This Layer Adds",
        "",
        "- Probabilistic Sharpe Ratio using skew/kurtosis-adjusted Sharpe uncertainty.",
        "- Deflated Sharpe Ratio proxy that raises the hurdle as the number of tested variants grows.",
        "- Bonferroni-style multiple-testing support adjustment.",
        "- Lightweight PBO proxy: top in-sample candidate is checked against median out-of-sample performance across purged subperiod splits.",
        "- Purged and embargoed CV split utilities for overlapping forward-label research.",
        "- Rolling-origin split utilities for causal validation.",
        "- Standard strategy summary: annual return, vol, Sharpe, max drawdown, Calmar, CVaR, skew, kurtosis, PSR, DSR proxy, drawdown pain, and turnover warning.",
        "",
        "## Honest Limitations",
        "",
        "- DSR is approximate because the true dependence structure across all tried variants is not fully known.",
        "- PBO is a proxy, not full CPCV, unless a future sprint supplies explicit combinatorial splits and a complete trial log.",
        "- Metrics from saved return files cannot prove absence of research selection bias; they only make the risk visible.",
        "- Statistical support is necessary but not sufficient: state behavior, turnover, hidden beta, cash exposure, and implementation simplicity still matter.",
        "",
        "## How Frontier Sprints Should Use It",
        "",
        "1. Use exact stabilized GGG wrapper output as benchmark.",
        "2. Count every tried variant as a trial, including rejected variants.",
        "3. Use purging/embargo whenever labels overlap future periods.",
        "4. Report PSR, DSR proxy, PBO proxy, and limitations in sprint summaries.",
        "5. Reject or downgrade ideas whose support disappears after multiple-testing adjustment.",
    ]
    (DOCS / "statistical_validation_layer.md").write_text("\n".join(lines) + "\n")


def write_report(audit: pd.DataFrame, trial_info: Dict[str, int], cv_check: Dict[str, float], files_scanned: int) -> None:
    top = audit.sort_values(["validation_verdict", "sharpe"], ascending=[True, False]).head(20)
    verdict_counts = audit["validation_verdict"].value_counts().reset_index()
    verdict_counts.columns = ["validation_verdict", "count"]
    lines = [
        "# Statistical Validation Audit Report",
        "",
        "Research-only audit across available strategy return files. This report does not promote any candidate.",
        "",
        "## Scope",
        "",
        f"- Return series scanned: `{files_scanned}`",
        f"- Approximate trial count from metrics/results files: `{trial_info['trial_count']}` across `{trial_info['trial_file_count']}` files.",
        f"- Purged CV sanity check folds: `{cv_check['folds']}`, max train/test overlap: `{cv_check['max_train_test_overlap']}`.",
        "",
        "## Verdict Counts",
        "",
        md_table(verdict_counts),
        "",
        "## Top Rows By Verdict Then Sharpe",
        "",
        md_table(top, ["candidate", "source_file", "annual_return", "sharpe", "max_drawdown", "cvar_5", "psr", "dsr_proxy", "multiple_testing_adjusted_support", "pbo_proxy", "validation_verdict"], 20),
        "",
        "## Interpretation",
        "",
        "- Treat `statistically_supported` as permission for deeper review, not promotion.",
        "- Treat `promising_but_underpowered` as a candidate for controlled holdout/bootstrap work.",
        "- Treat `overfit_risk` and `diagnostic_only` as research memory, not deployment evidence.",
        "- High trial counts should make future frontier sprints more skeptical, not more excited.",
        "",
        "## Limitations",
        "",
        "- The audit uses available saved returns and metrics files; it cannot reconstruct unlogged experiments.",
        "- The PBO value is a project-level proxy across a bounded return-file universe, not a full CPCV estimate.",
        "- Some research files are long-form and some are one-series files; the script standardizes what it can and skips unreadable files.",
    ]
    (DOCS / "statistical_validation_audit_report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    VALIDATION_OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    files = discover_return_files()
    if not files:
        raise SystemExit("No return files discovered; cannot run validation audit.")
    trial_info = count_trials()
    benchmark = load_benchmark(files)
    audit = audit_rows(files, trial_info["trial_count"], benchmark)
    audit.to_csv(VALIDATION_OUT / "statistical_validation_audit.csv", index=False)
    write_layer_doc()
    write_report(audit, trial_info, sanity_check_cv(), len(files))
    print(f"Wrote {rel(VALIDATION_OUT / 'statistical_validation_audit.csv')} rows={len(audit)}")
    print(f"Wrote {rel(DOCS / 'statistical_validation_layer.md')}")
    print(f"Wrote {rel(DOCS / 'statistical_validation_audit_report.md')}")


if __name__ == "__main__":
    main()
