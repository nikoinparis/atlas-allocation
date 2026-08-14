#!/usr/bin/env python3
"""
Build a point-in-time stock breadth panel when vetted inputs are installed.

This is an ingestion scaffold, not a downloader. It validates the expected
input files under data/stock_breadth/raw/ and exits successfully with a missing
input report when the files are absent.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "data" / "stock_breadth"
RAW = STOCK / "raw"
PROCESSED = STOCK / "processed"
METADATA = STOCK / "metadata"
INTERIM = STOCK / "interim"

for path in [RAW, PROCESSED, METADATA, INTERIM]:
    path.mkdir(parents=True, exist_ok=True)


INPUT_GROUPS = {
    "index_membership": {
        "paths": [RAW / "index_membership.parquet", RAW / "index_membership.csv"],
        "required": True,
        "required_columns": ["security_id", "ticker", "index_name", "membership_start", "membership_end"],
    },
    "stock_prices_daily": {
        "paths": [
            RAW / "stock_prices_daily.parquet",
            RAW / "stock_prices_daily.csv",
            RAW / "stock_prices_daily",
        ],
        "required": True,
        "required_columns": ["date", "security_id", "adjusted_close"],
    },
    "security_master": {
        "paths": [RAW / "security_master.csv", RAW / "security_master.parquet"],
        "required": True,
        "required_columns": ["security_id", "ticker", "name", "first_trade_date", "last_trade_date"],
    },
    "sector_classification": {
        "paths": [RAW / "sector_classification.csv", RAW / "sector_classification.parquet"],
        "required": False,
        "required_columns": ["security_id", "sector", "classification_start", "classification_end"],
    },
}


def is_template_file(path: Path) -> bool:
    """Return True for *_TEMPLATE.csv / *_TEMPLATE.parquet files — never treat as real input."""
    return "_TEMPLATE." in path.name


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and not is_template_file(path):
            return path
    return None


def check_sample_sentinel(name: str, df: pd.DataFrame) -> None:
    """Raise if any cell contains the SAMPLE_NOT_REAL sentinel — guards against accidental use of fake data."""
    for col in df.columns:
        if df[col].astype(str).str.contains("SAMPLE_NOT_REAL", na=False).any():
            raise ValueError(
                f"Input '{name}' contains SAMPLE_NOT_REAL sentinel values. "
                "This file is not real data. Replace it with a vetted point-in-time source."
            )


def read_table(path: Path) -> pd.DataFrame:
    if path.is_dir():
        parts = sorted(path.glob("*.parquet"))
        if not parts:
            raise FileNotFoundError(f"No parquet parts found under {path}")
        return pd.concat([pd.read_parquet(part) for part in parts], ignore_index=True)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported input type: {path}")


def templates_present() -> list[str]:
    """Return names of *_TEMPLATE.csv files found in the raw directory (informational only)."""
    return [p.name for p in RAW.glob("*_TEMPLATE.csv")]


def write_missing_inputs_report(missing_rows: list[dict]) -> None:
    report = pd.DataFrame(missing_rows)
    report.to_csv(METADATA / "missing_inputs_report.csv", index=False)
    print("PIT stock breadth inputs are not installed. Missing input report written to:")
    print(f"  {METADATA / 'missing_inputs_report.csv'}")
    found_templates = templates_present()
    if found_templates:
        print(f"NOTE: Template files found (ignored — not real data): {found_templates}")
        print("      Rename/copy real data exports to the non-TEMPLATE filenames listed in")
        print(f"      {RAW / 'README_FILL_THESE_FILES.md'}")
    for row in missing_rows:
        if row["required"] and row["status"] == "MISSING":
            print(f"  - required missing: {row['input_group']}  accepted: {row['accepted_paths']}")


def validate_required_columns(name: str, df: pd.DataFrame, required_columns: list[str]) -> list[dict]:
    rows = []
    missing = [col for col in required_columns if col not in df.columns]
    rows.append(
        {
            "check": f"{name}_required_columns",
            "status": "PASS" if not missing else "FAIL",
            "details": "all required columns present" if not missing else f"missing columns: {missing}",
        }
    )
    return rows


def validate_membership(membership: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    df = membership.copy()
    for col in ["membership_start", "membership_end"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    dup_cols = ["security_id", "index_name", "membership_start", "membership_end"]
    duplicate_count = int(df.duplicated(dup_cols).sum())
    invalid_dates = int(((df["membership_end"].notna()) & (df["membership_end"] < df["membership_start"])).sum())
    missing_start = int(df["membership_start"].isna().sum())

    rows.extend(
        [
            {
                "check": "membership_duplicate_rows",
                "status": "PASS" if duplicate_count == 0 else "FAIL",
                "details": f"duplicate rows={duplicate_count}",
            },
            {
                "check": "membership_start_end_order",
                "status": "PASS" if invalid_dates == 0 and missing_start == 0 else "FAIL",
                "details": f"invalid end-before-start rows={invalid_dates}; missing starts={missing_start}",
            },
        ]
    )
    return rows


def validate_prices(prices: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["adjusted_close"] = pd.to_numeric(df["adjusted_close"], errors="coerce")
    bad_dates = int(df["date"].isna().sum())
    bad_prices = int((df["adjusted_close"].isna() | (df["adjusted_close"] <= 0)).sum())
    duplicate_count = int(df.duplicated(["date", "security_id"]).sum())
    rows.extend(
        [
            {
                "check": "price_date_and_adjusted_close_quality",
                "status": "PASS" if bad_dates == 0 and bad_prices == 0 else "FAIL",
                "details": f"bad dates={bad_dates}; nonpositive/missing adjusted_close={bad_prices}",
            },
            {
                "check": "price_duplicate_security_date",
                "status": "PASS" if duplicate_count == 0 else "FAIL",
                "details": f"duplicate security/date rows={duplicate_count}",
            },
        ]
    )
    return rows


def build_weekly_breadth(membership: pd.DataFrame, prices: pd.DataFrame, sectors: pd.DataFrame | None) -> None:
    membership = membership.copy()
    prices = prices.copy()
    membership["membership_start"] = pd.to_datetime(membership["membership_start"], errors="coerce")
    membership["membership_end"] = pd.to_datetime(membership["membership_end"], errors="coerce")
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["adjusted_close"] = pd.to_numeric(prices["adjusted_close"], errors="coerce")
    prices = prices.dropna(subset=["date", "security_id", "adjusted_close"])
    prices = prices[prices["adjusted_close"] > 0].sort_values(["security_id", "date"])

    daily = prices.pivot_table(index="date", columns="security_id", values="adjusted_close", aggfunc="last").sort_index()
    daily.columns = daily.columns.astype(str)
    weekly = daily.resample("W-FRI").last().dropna(how="all")
    daily_returns = daily.pct_change()
    weekly_returns = weekly.pct_change()

    above_50d = (daily > daily.rolling(50, min_periods=40).mean()).resample("W-FRI").last()
    above_100d = (daily > daily.rolling(100, min_periods=80).mean()).resample("W-FRI").last()
    above_200d = (daily > daily.rolling(200, min_periods=160).mean()).resample("W-FRI").last()
    pos_13w = weekly.pct_change(13) > 0
    pos_26w = weekly.pct_change(26) > 0
    high_13w = weekly >= weekly.rolling(13, min_periods=10).max()
    high_52w = weekly >= weekly.rolling(52, min_periods=40).max()
    drawdown = weekly / weekly.rolling(52, min_periods=20).max() - 1.0
    dd_lt_10 = drawdown > -0.10
    median_return_13w = weekly.pct_change(13).median(axis=1)

    rows = []
    for week in weekly.index:
        active = membership[
            (membership["membership_start"] <= week)
            & (membership["membership_end"].isna() | (membership["membership_end"] >= week))
        ]["security_id"].astype(str)
        members = [sid for sid in active if sid in weekly.columns]
        if not members:
            rows.append({"date": week, "active_member_count": 0})
            continue
        member_weekly_returns = weekly_returns.reindex(columns=members).loc[week]
        row = {
            "date": week,
            "active_member_count": len(members),
            "pct_members_above_50d_ma": float(above_50d.reindex(columns=members).loc[week].mean()),
            "pct_members_above_100d_ma": float(above_100d.reindex(columns=members).loc[week].mean()),
            "pct_members_above_200d_ma": float(above_200d.reindex(columns=members).loc[week].mean()),
            "pct_members_positive_13w_return": float(pos_13w.reindex(columns=members).loc[week].mean()),
            "pct_members_positive_26w_return": float(pos_26w.reindex(columns=members).loc[week].mean()),
            "pct_members_at_13w_high": float(high_13w.reindex(columns=members).loc[week].mean()),
            "pct_members_at_52w_high": float(high_52w.reindex(columns=members).loc[week].mean()),
            "pct_members_in_drawdown_less_than_10pct": float(dd_lt_10.reindex(columns=members).loc[week].mean()),
            "equal_weight_member_return": float(member_weekly_returns.mean()),
            "median_member_return_13w": float(weekly.pct_change(13).reindex(columns=members).loc[week].median()),
        }
        rows.append(row)

    panel = pd.DataFrame(rows).set_index("date").sort_index()
    panel["breadth_thrust_4w"] = panel["pct_members_above_50d_ma"] - panel["pct_members_above_50d_ma"].shift(4)
    panel["breadth_thrust_8w"] = panel["pct_members_above_50d_ma"] - panel["pct_members_above_50d_ma"].shift(8)
    panel["broad_bull_flag"] = (
        (panel["pct_members_above_200d_ma"] >= 0.65)
        & (panel["pct_members_positive_26w_return"] >= 0.60)
        & (panel["breadth_thrust_4w"] >= -0.05)
    ).astype(int)
    panel["narrow_bull_warning"] = (
        (panel["pct_members_above_200d_ma"] < 0.45)
        & (panel["pct_members_positive_26w_return"] < 0.45)
    ).astype(int)
    feature_cols = [col for col in panel.columns if col not in {"active_member_count"}]
    for col in feature_cols:
        panel[f"{col}_lag1w"] = panel[col].shift(1)
    panel.to_csv(PROCESSED / "stock_breadth_weekly.csv")

    if sectors is not None and not sectors.empty:
        sector_df = sectors.copy()
        sector_df["classification_start"] = pd.to_datetime(sector_df["classification_start"], errors="coerce")
        sector_df["classification_end"] = pd.to_datetime(sector_df["classification_end"], errors="coerce")
        sector_rows = []
        for week in weekly.index:
            active_members = membership[
                (membership["membership_start"] <= week)
                & (membership["membership_end"].isna() | (membership["membership_end"] >= week))
            ][["security_id"]]
            active_sectors = sector_df[
                (sector_df["classification_start"] <= week)
                & (sector_df["classification_end"].isna() | (sector_df["classification_end"] >= week))
            ][["security_id", "sector"]]
            merged = active_members.merge(active_sectors, on="security_id", how="left").dropna(subset=["sector"])
            for sector, group in merged.groupby("sector"):
                members = [sid for sid in group["security_id"].astype(str) if sid in weekly.columns]
                if not members:
                    continue
                sector_rows.append(
                    {
                        "date": week,
                        "sector": sector,
                        "active_member_count": len(members),
                        "pct_members_above_200d_ma": float(above_200d.reindex(columns=members).loc[week].mean()),
                        "pct_members_positive_26w_return": float(pos_26w.reindex(columns=members).loc[week].mean()),
                        "equal_weight_member_return": float(weekly_returns.reindex(columns=members).loc[week].mean()),
                    }
                )
        pd.DataFrame(sector_rows).to_csv(PROCESSED / "stock_breadth_by_sector_weekly.csv", index=False)


def main() -> None:
    missing_rows = []
    paths: dict[str, Path | None] = {}
    for name, spec in INPUT_GROUPS.items():
        existing = first_existing(spec["paths"])
        paths[name] = existing
        missing_rows.append(
            {
                "input_group": name,
                "required": bool(spec["required"]),
                "status": "FOUND" if existing is not None else "MISSING",
                "resolved_path": str(existing.relative_to(ROOT)) if existing is not None else "",
                "accepted_paths": " | ".join(str(p.relative_to(ROOT)) for p in spec["paths"]),
                "required_columns": " | ".join(spec["required_columns"]),
            }
        )

    required_missing = [row for row in missing_rows if row["required"] and row["status"] == "MISSING"]
    if required_missing:
        write_missing_inputs_report(missing_rows)
        return

    loaded: dict[str, pd.DataFrame] = {}
    quality_rows: list[dict] = []
    for name, spec in INPUT_GROUPS.items():
        if paths[name] is None:
            continue
        df = read_table(paths[name])
        check_sample_sentinel(name, df)
        loaded[name] = df
        quality_rows.extend(validate_required_columns(name, df, spec["required_columns"]))

    if any(row["status"] == "FAIL" for row in quality_rows):
        pd.DataFrame(quality_rows).to_csv(METADATA / "data_quality_report.csv", index=False)
        print("Input schema validation failed. See data_quality_report.csv.")
        return

    quality_rows.extend(validate_membership(loaded["index_membership"]))
    quality_rows.extend(validate_prices(loaded["stock_prices_daily"]))
    pd.DataFrame(quality_rows).to_csv(METADATA / "data_quality_report.csv", index=False)
    if any(row["status"] == "FAIL" for row in quality_rows):
        print("Input data validation failed. See data_quality_report.csv.")
        return

    build_weekly_breadth(
        loaded["index_membership"],
        loaded["stock_prices_daily"],
        loaded.get("sector_classification"),
    )
    print("Built PIT stock breadth panel:")
    print(PROCESSED / "stock_breadth_weekly.csv")
    if (PROCESSED / "stock_breadth_by_sector_weekly.csv").exists():
        print(PROCESSED / "stock_breadth_by_sector_weekly.csv")


if __name__ == "__main__":
    main()
