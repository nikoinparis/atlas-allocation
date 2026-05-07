#!/usr/bin/env python3
"""
Phase 5A - Point-in-Time Stock Breadth Data Upgrade Plan and Scaffold.

This phase creates data requirements, storage conventions, validation gates,
and a future Phase 5B prompt outline. It does not download stock data, build
portfolio candidates, or modify production/shadow pins.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PHASE5 = ROOT / "data" / "research" / "phase_5_true_stock_breadth_data_upgrade"
OUT = ROOT / "data" / "research" / "phase_5a_pit_stock_breadth_data_scaffold"
STOCK = ROOT / "data" / "stock_breadth"
RAW = STOCK / "raw"
INTERIM = STOCK / "interim"
PROCESSED = STOCK / "processed"
METADATA = STOCK / "metadata"
REPORT = ROOT / "docs" / "research" / "2026-05-07_phase_5a_pit_stock_breadth_data_scaffold_report.md"
PHASE5B_PROMPT = OUT / "phase5a_phase5b_prompt_outline.md"
README = STOCK / "README.md"

for path in [OUT, RAW, INTERIM, PROCESSED, METADATA]:
    path.mkdir(parents=True, exist_ok=True)

COMMANDS_EXECUTED = [
    "pwd",
    "git status --short",
    "git branch --show-current",
    "git worktree list",
    "find .. -name CLAUDE.md -maxdepth 3",
    "sed -n '1,260p' CLAUDE.md",
    "test -f docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md && test -d data/research/phase_5_true_stock_breadth_data_upgrade && test -f data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv",
    "sed -n '1,240p' docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md",
    "find data/research/phase_5_true_stock_breadth_data_upgrade -maxdepth 1 -type f | sort",
    "python3 - <<'PY'  # small pandas summaries of phase5_data_gap_report.csv, phase5_stock_breadth_source_audit.csv, phase5_survivorship_bias_risk_register.csv, phase5_next_phase_decision.csv",
    "find data/01_data_hub -maxdepth 2 -type f | sort | head -n 120",
    "find data/04_layer2b_risk_regime_engine -maxdepth 2 -type f | sort | head -n 120",
    "sed -n '1,260p' .gitignore",
    "rg -n \"yfinance|yf\\.download|download|weekly_prices|daily_prices|parquet|to_parquet|read_parquet|data/01_data_hub|public/dashboard-data\" scripts notebooks data docs -g '!data/research/phase_ooo_signal_discovery/**' -g '!data/research/phase_ppp_latent_factor_discovery/**' -g '!data/research/phase_qqq_deep_feature_interaction_mining/**' -g '!data/research/phase_sss*/**'",
    "web source checks for Norgate, CRSP, Nasdaq Data Link/Sharadar, Alpha Vantage, Polygon, S&P DJI",
    "python3 -m py_compile scripts/build_pit_stock_breadth_panel.py scripts/phase_5a_pit_stock_breadth_data_scaffold.py",
    "python3 scripts/build_pit_stock_breadth_panel.py",
    "python3 scripts/phase_5a_pit_stock_breadth_data_scaffold.py",
]


def save_csv(name: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.to_csv(OUT / name, index=False)
    return df


def md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df.head(max_rows)
    try:
        return small.to_markdown(index=False)
    except Exception:
        return "```\n" + small.to_string(index=False) + "\n```"


def build_requirements() -> dict[str, pd.DataFrame]:
    requirements = save_csv(
        "phase5a_pit_data_requirements.csv",
        [
            {
                "dataset": "point_in_time_index_membership",
                "priority": "REQUIRED",
                "preferred_scope": "S&P 500 full history; Nasdaq-100 optional",
                "minimum_fields": "security_id,ticker,index_name,membership_start,membership_end,effective_date,source",
                "causal_requirement": "membership row can only affect breadth on/after effective date, lagged at least one rebalance period if publication timing is uncertain",
                "bias_risk_if_missing": "HIGH: current-constituent backfill creates survivorship and lookahead bias",
                "phase5b_use": "define active members for each week before calculating breadth",
            },
            {
                "dataset": "adjusted_stock_prices",
                "priority": "REQUIRED",
                "preferred_scope": "daily adjusted close for all active and delisted historical members",
                "minimum_fields": "date,security_id,ticker,adjusted_close,close,volume,split_factor,dividend_amount,delisting_return",
                "causal_requirement": "weekly features use prices available through week t; signals use lagged t+1 columns",
                "bias_risk_if_missing": "HIGH: omitting dead/delisted stocks overstates historical breadth",
                "phase5b_use": "moving-average, momentum, high, drawdown, and equal-weight breadth features",
            },
            {
                "dataset": "ticker_security_identity_mapping",
                "priority": "REQUIRED",
                "preferred_scope": "permanent id such as PERMNO/vendor id with ticker history",
                "minimum_fields": "security_id,permanent_id_source,ticker,name,exchange,first_trade_date,last_trade_date,delisting_date",
                "causal_requirement": "ticker changes must map to the same security without retroactive symbol leakage",
                "bias_risk_if_missing": "HIGH: ticker-only joins break on mergers, ticker reuse, and class changes",
                "phase5b_use": "stable joins among membership, prices, sector, and delisting records",
            },
            {
                "dataset": "sector_classification",
                "priority": "PREFERRED",
                "preferred_scope": "point-in-time GICS sector/industry history",
                "minimum_fields": "security_id,sector,industry,classification_start,classification_end,classification_system,source",
                "causal_requirement": "classification active for week t only if known/effective by week t",
                "bias_risk_if_missing": "MEDIUM: static sectors are acceptable only with research caveat",
                "phase5b_use": "sector-level stock breadth and broad-vs-narrow leadership checks",
            },
            {
                "dataset": "publication_and_lag_assumptions",
                "priority": "REQUIRED_METADATA",
                "preferred_scope": "source manifest with update schedule, timezone, publication lag, and revision policy",
                "minimum_fields": "source_name,download_date,coverage_start,coverage_end,publication_lag_rule,license_notes",
                "causal_requirement": "apply at least 1-week signal lag; membership uncertainty should add one rebalance-period lag",
                "bias_risk_if_missing": "MEDIUM/HIGH: unclear publication timing can create silent lookahead",
                "phase5b_use": "document why each feature is tradable at the next rebalance",
            },
        ],
    )

    schemas = {
        "phase5a_required_schema_index_membership.csv": [
            ("security_id", "string", True, "stable vendor/permanent security id", "non-null; stable across ticker changes"),
            ("ticker", "string", True, "ticker active during membership interval", "non-null; not used as sole join key"),
            ("index_name", "string", True, "S&P 500 or Nasdaq-100", "controlled vocabulary"),
            ("membership_start", "date", True, "effective membership start date", "must be <= membership_end when end exists"),
            ("membership_end", "date", True, "effective membership end date; blank if still active", "blank or >= membership_start"),
            ("announcement_date", "date", False, "announcement date if available", "if after effective date, use conservative lag"),
            ("source", "string", True, "vendor/source identifier", "non-null"),
        ],
        "phase5a_required_schema_stock_prices.csv": [
            ("date", "date", True, "trading date", "non-null market date"),
            ("security_id", "string", True, "stable id matching membership", "non-null"),
            ("ticker", "string", False, "ticker as of date", "informational only"),
            ("adjusted_close", "float", True, "split/dividend-adjusted close", "> 0"),
            ("close", "float", False, "raw close", "> 0 if present"),
            ("volume", "float", False, "daily volume", ">= 0 if present"),
            ("delisting_return", "float", False, "delisting return if applicable", "document missing policy"),
            ("adjustment_source", "string", True, "adjustment methodology/source", "non-null"),
        ],
        "phase5a_required_schema_stock_metadata.csv": [
            ("security_id", "string", True, "stable id", "unique"),
            ("permanent_id_source", "string", True, "CRSP/Norgate/Sharadar/etc.", "non-null"),
            ("ticker", "string", True, "latest or primary ticker", "non-null"),
            ("name", "string", True, "company/security name", "non-null"),
            ("exchange", "string", False, "primary exchange", "document missing"),
            ("first_trade_date", "date", True, "first available trading date", "non-null"),
            ("last_trade_date", "date", True, "last available trading date", ">= first_trade_date"),
            ("delisting_date", "date", False, "delisting date when applicable", "must align with prices"),
        ],
        "phase5a_required_schema_sector_classification.csv": [
            ("security_id", "string", True, "stable id", "non-null"),
            ("sector", "string", True, "GICS or vendor sector", "non-null"),
            ("industry", "string", False, "GICS industry or equivalent", "optional"),
            ("classification_start", "date", True, "effective classification start", "non-null"),
            ("classification_end", "date", True, "effective classification end; blank if current", "blank or >= start"),
            ("classification_system", "string", True, "GICS/vendor/static", "non-null"),
            ("source", "string", True, "vendor/source identifier", "non-null"),
        ],
    }
    schema_frames = {}
    for file_name, rows in schemas.items():
        schema_frames[file_name] = save_csv(
            file_name,
            [
                {
                    "column_name": col,
                    "dtype": dtype,
                    "required": required,
                    "description": desc,
                    "validation_rule": rule,
                }
                for col, dtype, required, desc, rule in rows
            ],
        )
    return {"requirements": requirements, **schema_frames}


def build_source_audit() -> dict[str, pd.DataFrame]:
    audit = save_csv(
        "phase5a_data_source_option_audit.csv",
        [
            {
                "source": "Existing local repo data",
                "available_now_in_repo": True,
                "point_in_time_membership": False,
                "delisted_stock_coverage": False,
                "adjusted_prices": False,
                "sector_classification": False,
                "ticker_history_or_perm_id": False,
                "expected_bias_risk": "UNUSABLE_FOR_STOCK_BREADTH",
                "cost_or_access_notes": "Already inspected; only ETF data and ETF/sector breadth exist.",
                "implementation_complexity": "none",
                "production_decision_safe": False,
                "research_only_safe": False,
                "recommended_role": "Do not use for true stock breadth.",
                "verification_status": "verified locally",
                "reference_url": "",
            },
            {
                "source": "Norgate Data US Stocks Platinum/Diamond",
                "available_now_in_repo": False,
                "point_in_time_membership": True,
                "delisted_stock_coverage": True,
                "adjusted_prices": True,
                "sector_classification": "needs manual verification",
                "ticker_history_or_perm_id": "vendor symbol plus delisted suffix; permanent-id behavior needs manual verification",
                "expected_bias_risk": "LOW if index constituent plugin and delisted database are used correctly",
                "cost_or_access_notes": "Paid subscription; official pages say delisted stocks and historical constituent access require Platinum/Diamond.",
                "implementation_complexity": "medium",
                "production_decision_safe": "Yes after license, schema, and lag audit",
                "research_only_safe": True,
                "recommended_role": "Most practical non-institutional path if user can subscribe.",
                "verification_status": "official docs checked; details still require manual subscription/API verification",
                "reference_url": "https://norgatedata.com/data-content-tables.php; https://norgatedata.com/index.php/pricing/",
            },
            {
                "source": "CRSP / Compustat via WRDS",
                "available_now_in_repo": False,
                "point_in_time_membership": "needs manual verification for chosen index constituent table",
                "delisted_stock_coverage": True,
                "adjusted_prices": True,
                "sector_classification": "available through Compustat/GICS if licensed; needs manual verification",
                "ticker_history_or_perm_id": True,
                "expected_bias_risk": "LOW if PERMNO/PERMCO, delisting returns, and PIT membership are joined correctly",
                "cost_or_access_notes": "Institutional/academic access usually required.",
                "implementation_complexity": "high",
                "production_decision_safe": "Yes after access and reproducible export",
                "research_only_safe": True,
                "recommended_role": "Highest-quality institutional path if user has WRDS access.",
                "verification_status": "CRSP guide checked for PERMNO and delisting fields; index membership access needs manual verification",
                "reference_url": "https://www.crsp.org/wp-content/uploads/guides/CRSP10_Year_US_Stock_Database_Guide.pdf",
            },
            {
                "source": "Nasdaq Data Link / Sharadar",
                "available_now_in_repo": False,
                "point_in_time_membership": "needs manual verification",
                "delisted_stock_coverage": True,
                "adjusted_prices": True,
                "sector_classification": "needs manual verification",
                "ticker_history_or_perm_id": "needs manual verification",
                "expected_bias_risk": "LOW/MEDIUM depending on PIT constituent availability and ticker mapping",
                "cost_or_access_notes": "Paid vendor feeds; official pages indicate Sharadar has active/delisted stock coverage.",
                "implementation_complexity": "medium/high",
                "production_decision_safe": "Only if PIT membership and delisting methodology are verified",
                "research_only_safe": True,
                "recommended_role": "Candidate path if it can provide historical index membership or a safe proxy universe.",
                "verification_status": "official docs checked; PIT constituent specifics need manual verification",
                "reference_url": "https://www.sharadar.com/; https://help.data.nasdaq.com/article/508-do-you-cover-delisted-stocks",
            },
            {
                "source": "Polygon / Tiingo / Alpha Vantage / yfinance with current constituents",
                "available_now_in_repo": False,
                "point_in_time_membership": False,
                "delisted_stock_coverage": "partial/varies by vendor; not enough for index PIT breadth without membership",
                "adjusted_prices": "varies; Alpha Vantage and Polygon expose adjusted price endpoints/flags",
                "sector_classification": "varies or absent",
                "ticker_history_or_perm_id": "varies; needs manual verification",
                "expected_bias_risk": "HIGH if paired with today's constituents",
                "cost_or_access_notes": "Can be cheap and API-friendly, but not sufficient for promotable PIT index breadth.",
                "implementation_complexity": "medium",
                "production_decision_safe": False,
                "research_only_safe": "Diagnostic only with explicit SURVIVORSHIP_BIASED label",
                "recommended_role": "Do not use for production decisions; optional tiny diagnostic after PIT path is decided.",
                "verification_status": "official docs checked for Alpha Vantage listing status and Polygon ticker active flag; PIT index membership absent",
                "reference_url": "https://www.alphavantage.co/documentation/; https://polygon.io/docs/rest/stocks/tickers/all-tickers",
            },
            {
                "source": "Wikipedia/current index constituents",
                "available_now_in_repo": False,
                "point_in_time_membership": False,
                "delisted_stock_coverage": False,
                "adjusted_prices": False,
                "sector_classification": "current/static only",
                "ticker_history_or_perm_id": False,
                "expected_bias_risk": "HIGH",
                "cost_or_access_notes": "Free current constituent list and partial changes table, but not a validated PIT stock data system.",
                "implementation_complexity": "low",
                "production_decision_safe": False,
                "research_only_safe": "Diagnostic only",
                "recommended_role": "Use only for UI/schema dry runs, never historical truth.",
                "verification_status": "needs manual verification if used",
                "reference_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            },
            {
                "source": "Vendor breadth indexes",
                "available_now_in_repo": False,
                "point_in_time_membership": "not exposed at member level",
                "delisted_stock_coverage": "depends on vendor methodology",
                "adjusted_prices": "not applicable if breadth series only",
                "sector_classification": "depends on vendor series",
                "ticker_history_or_perm_id": False,
                "expected_bias_risk": "LOW/MEDIUM if methodology and historical revisions are documented",
                "cost_or_access_notes": "May be easier than full stock panel but less auditable and less flexible.",
                "implementation_complexity": "low/medium",
                "production_decision_safe": "Only after methodology, revisions, and publication lag are documented",
                "research_only_safe": True,
                "recommended_role": "Secondary option for classifier features if member-level panel is unavailable.",
                "verification_status": "needs manual vendor verification",
                "reference_url": "",
            },
            {
                "source": "Manual small diagnostic current-constituent sample",
                "available_now_in_repo": False,
                "point_in_time_membership": False,
                "delisted_stock_coverage": False,
                "adjusted_prices": "could be fetched but not in this phase",
                "sector_classification": "current/static only",
                "ticker_history_or_perm_id": False,
                "expected_bias_risk": "HIGH",
                "cost_or_access_notes": "Cheap but non-promotable.",
                "implementation_complexity": "low",
                "production_decision_safe": False,
                "research_only_safe": "Diagnostic only",
                "recommended_role": "Use only to test code mechanics after scaffold is accepted.",
                "verification_status": "not used",
                "reference_url": "",
            },
        ],
    )
    path = save_csv(
        "phase5a_recommended_data_source_path.csv",
        [
            {
                "rank": 1,
                "path": "Norgate Data US Stocks Platinum/Diamond",
                "when_to_choose": "User wants a practical desktop/vendor workflow and can subscribe.",
                "why": "Combines historical daily data, delisted stock coverage, and historical constituent access in one vendor path.",
                "blocking_manual_checks": "Confirm Python/export access, schema fields, sector support, license, and how historical constituent plugin exposes effective dates.",
            },
            {
                "rank": 2,
                "path": "CRSP / Compustat via WRDS",
                "when_to_choose": "User has university/institutional WRDS access.",
                "why": "Best institutional identity/delisting framework via PERMNO/PERMCO and delisting return fields.",
                "blocking_manual_checks": "Confirm PIT S&P 500/Nasdaq constituent table access and export workflow.",
            },
            {
                "rank": 3,
                "path": "Sharadar/Nasdaq Data Link",
                "when_to_choose": "User already has Sharadar/Nasdaq subscription and can verify PIT membership.",
                "why": "Active/delisted stock coverage appears promising, but constituent membership must be verified before promotion.",
                "blocking_manual_checks": "Confirm historical index membership, delisting returns/adjustments, ticker mapping, and sector history.",
            },
            {
                "rank": 4,
                "path": "Current constituents plus yfinance/API",
                "when_to_choose": "Only for code-path smoke tests.",
                "why": "Survivorship-biased and not promotable.",
                "blocking_manual_checks": "Must label all outputs SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY.",
            },
        ],
    )
    return {"audit": audit, "recommended_path": path}


def write_readme() -> None:
    README.write_text(
        """# Point-in-Time Stock Breadth Data

This folder is reserved for future point-in-time stock breadth inputs and
processed breadth summaries. Phase 5A creates the scaffold only. It does not
install, download, or fabricate stock data.

## Expected Layout

- `raw/index_membership.parquet` or `raw/index_membership.csv`
- `raw/stock_prices_daily.parquet`, `raw/stock_prices_daily.csv`, or partitioned `raw/stock_prices_daily/`
- `raw/security_master.csv`
- `raw/sector_classification.csv`
- `interim/` for temporary normalized extracts
- `processed/stock_breadth_weekly.csv`
- `processed/stock_breadth_by_sector_weekly.csv`
- `metadata/source_manifest.csv`
- `metadata/data_quality_report.csv`
- `metadata/bias_risk_register.csv`
- `metadata/missing_inputs_report.csv`

## Required Rules

Use point-in-time index membership with effective start/end dates. Do not use
today's S&P 500 or Nasdaq-100 constituents as historical truth. Current
constituent diagnostics must be labeled `SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY`
and cannot support production or shadow promotion.

Daily prices must include split/dividend-adjusted close values. Delisted and
dead stocks should be included wherever possible, and delisting return handling
must be documented in `metadata/source_manifest.csv`.

Use a stable security id. Ticker alone is not enough because tickers change,
merge, disappear, and get reused.

All breadth features must be causal. Features through week `t` can only be used
as portfolio signals after an explicit one-week lag, e.g. `feature_lag1w`.

## Git And File Size

Never commit files over GitHub's 100 MB limit. Large raw stock panels should
stay local, use Git LFS, or live in external storage. Normal git should only
track this README, small source manifests, schema files, validation reports, and
small processed summaries after their size is checked.

Recommended future `.gitignore` rules, not applied automatically in Phase 5A:

```gitignore
data/stock_breadth/raw/*.parquet
data/stock_breadth/raw/stock_prices_daily/
data/stock_breadth/interim/
data/stock_breadth/processed/*.parquet
```
""",
        encoding="utf-8",
    )


def build_storage_plan() -> dict[str, pd.DataFrame]:
    write_readme()
    storage = save_csv(
        "phase5a_local_storage_plan.csv",
        [
            {
                "path": "data/stock_breadth/raw/index_membership.parquet",
                "purpose": "PIT S&P 500/Nasdaq membership intervals",
                "format": "parquet preferred; csv accepted by scaffold",
                "commit_policy": "avoid committing if large; commit only small samples/manifests",
            },
            {
                "path": "data/stock_breadth/raw/stock_prices_daily.parquet or partitioned directory",
                "purpose": "daily adjusted stock prices for active and delisted historical members",
                "format": "partitioned parquet preferred",
                "commit_policy": "keep local/external/LFS; do not normal-git commit large raw panel",
            },
            {
                "path": "data/stock_breadth/raw/security_master.csv",
                "purpose": "stable identity mapping and ticker history",
                "format": "csv acceptable if small",
                "commit_policy": "can commit if license permits and file is small",
            },
            {
                "path": "data/stock_breadth/raw/sector_classification.csv",
                "purpose": "sector/GICS classification intervals",
                "format": "csv or parquet",
                "commit_policy": "can commit if license permits and file is small",
            },
            {
                "path": "data/stock_breadth/processed/stock_breadth_weekly.csv",
                "purpose": "weekly aggregate stock breadth signals",
                "format": "csv",
                "commit_policy": "commit only after size and bias checks pass",
            },
            {
                "path": "data/stock_breadth/metadata/missing_inputs_report.csv",
                "purpose": "safe scaffold status when data is absent",
                "format": "csv",
                "commit_policy": "safe to commit",
            },
        ],
    )
    git_plan = save_csv(
        "phase5a_git_large_file_plan.csv",
        [
            {
                "item": "raw daily stock price panel",
                "risk": "likely over GitHub 100 MB limit",
                "recommendation": "store outside git, partition parquet locally, or use Git LFS if repository policy allows",
                "gitignore_change": "recommend only; do not modify .gitignore in Phase 5A",
            },
            {
                "item": "processed weekly breadth panel",
                "risk": "probably small if aggregate-only",
                "recommendation": "check size before committing; keep member-level wide panels out of normal git",
                "gitignore_change": "none now",
            },
            {
                "item": "metadata and validation reports",
                "risk": "small",
                "recommendation": "safe to commit if license permits",
                "gitignore_change": "none",
            },
            {
                "item": "current-constituent diagnostics",
                "risk": "bias and possible large downloads",
                "recommendation": "avoid unless explicitly labeled diagnostic-only",
                "gitignore_change": "keep raw diagnostics local",
            },
        ],
    )
    return {"storage": storage, "git_plan": git_plan}


def build_validation_and_classifier_plan() -> dict[str, pd.DataFrame]:
    checklist_items = [
        ("point_in_time_membership_only", "Membership rows include effective start/end dates and active members are selected as of week t only."),
        ("no_current_constituent_backfill", "No current S&P 500/Nasdaq list is used as a historical universe."),
        ("no_future_membership_additions", "A future addition cannot enter active membership before its effective date plus lag rule."),
        ("no_delisted_stock_omission", "Delisted/dead members are represented or omission is explicitly blocking production use."),
        ("price_adjustment_documented", "Split/dividend/delisting adjustment method is documented."),
        ("ticker_changes_mapped", "Ticker changes map through stable security id."),
        ("duplicate_security_ids_handled", "Duplicate ticker/security/date rows are absent or resolved deterministically."),
        ("sector_classifications_timestamped", "Sector intervals are PIT or static caveat is explicitly recorded."),
        ("signal_lag_applied", "All features have lag1w columns used for portfolio signals."),
        ("no_centered_rolling_windows", "All rolling calculations are trailing only."),
        ("no_future_returns_in_features", "Forward returns appear only in validation outputs, never features."),
        ("no_random_train_test_split", "Validation is time ordered."),
        ("coverage_by_week", "Active member count and price coverage are reported by week."),
        ("missing_price_rate_by_week", "Weekly missing price rate is below acceptance threshold or caveated."),
        ("delisting_count_by_year", "Delisting count by year is reconciled if vendor supplies it."),
        ("membership_turnover_sanity", "Additions/removals by year are plausible and source-aligned."),
        ("compare_stock_vs_etf_breadth", "Stock breadth is compared to Phase 4B ETF/sector breadth."),
        ("compare_index_vs_equal_weight", "Broad index return is compared to equal-weight member return."),
    ]
    checklist = save_csv(
        "phase5a_bias_leakage_validation_checklist.csv",
        [
            {
                "check_id": check_id,
                "required_for_phase5b": True,
                "description": description,
                "failure_action": "block production/shadow promotion; research-only at most",
            }
            for check_id, description in checklist_items
        ],
    )
    tests = save_csv(
        "phase5a_future_acceptance_tests.csv",
        [
            {
                "test_id": "missing_inputs_exit_zero",
                "scope": "ingestion scaffold",
                "acceptance_rule": "script exits 0 and writes metadata/missing_inputs_report.csv when raw inputs are absent",
            },
            {
                "test_id": "schema_required_columns",
                "scope": "all raw tables",
                "acceptance_rule": "all required schema columns present before feature build",
            },
            {
                "test_id": "membership_date_order",
                "scope": "index membership",
                "acceptance_rule": "membership_start exists and membership_end is blank or >= start",
            },
            {
                "test_id": "duplicate_membership_rows",
                "scope": "index membership",
                "acceptance_rule": "no duplicate security/index/start/end rows",
            },
            {
                "test_id": "weekly_active_member_count",
                "scope": "built panel",
                "acceptance_rule": "active member count is plausible by week and not a constant current-constituent backfill",
            },
            {
                "test_id": "lag_columns_exist",
                "scope": "built panel",
                "acceptance_rule": "all signal fields have explicit *_lag1w equivalents",
            },
            {
                "test_id": "no_phase5b_without_bias_pass",
                "scope": "research governance",
                "acceptance_rule": "candidate builds are blocked until source, bias, and alignment checks pass",
            },
        ],
    )
    classifier = save_csv(
        "phase5a_market_state_classifier_redesign_plan.csv",
        [
            {
                "classifier_area": "neutral_mixed_split",
                "future_labels": "neutral_stock_risk_on | neutral_chop | neutral_deteriorating | neutral_recovery_setup",
                "stock_breadth_inputs": "pct above 200d, positive 13w/26w returns, breadth thrust, narrow warning",
                "intended_effect": "reduce unnecessary BIL only in broad neutral risk-on weeks",
                "states_unchanged": "stressed_panic remains unchanged",
            },
            {
                "classifier_area": "bull_quality",
                "future_labels": "broad_bull | narrow_bull | defensive_bull | late_cycle_bull | fake_recovery",
                "stock_breadth_inputs": "stock breadth level, sector breadth, index-vs-equal-weight divergence, defensive leadership",
                "intended_effect": "distinguish strong broad bull from QQQ/SPY-only narrow market",
                "states_unchanged": "stressed_panic remains unchanged",
            },
            {
                "classifier_area": "recovery_rerisk",
                "future_labels": "recovery_confirmed_breadth_strong | recovery_confirmed_breadth_weak | recovery_fragile_fakeout",
                "stock_breadth_inputs": "breadth thrust 4w/8w, percentage above MA, active member count improvement",
                "intended_effect": "re-risk faster only when recovery has broad participation",
                "states_unchanged": "recovery_fragile cautious unless separately confirmed",
            },
        ],
    )
    aggression = save_csv(
        "phase5a_aggression_score_design.csv",
        [
            {
                "component": "breadth_level",
                "weight": 0.30,
                "inputs": "pct_members_above_200d_ma_lag1w, pct_members_positive_26w_return_lag1w",
                "interpretation": "higher when broad market participation is strong",
            },
            {
                "component": "breadth_thrust",
                "weight": 0.20,
                "inputs": "breadth_thrust_4w_lag1w, breadth_thrust_8w_lag1w",
                "interpretation": "higher when participation is improving",
            },
            {
                "component": "sector_confirmation",
                "weight": 0.15,
                "inputs": "sector-level breadth dispersion and number of sectors above thresholds",
                "interpretation": "blocks narrow single-sector leadership from looking broad",
            },
            {
                "component": "volatility_containment",
                "weight": 0.15,
                "inputs": "existing VIX/regime volatility features",
                "interpretation": "reduces aggression when market risk is elevated",
            },
            {
                "component": "credit_and_risk_appetite",
                "weight": 0.10,
                "inputs": "existing canary/credit ETF breadth features",
                "interpretation": "requires risk appetite confirmation",
            },
            {
                "component": "state_stability",
                "weight": 0.10,
                "inputs": "weeks since state transition and no recovery_fragile/stressed_panic",
                "interpretation": "penalizes unstable transitions",
            },
        ],
    )
    mapping = save_csv(
        "phase5a_future_portfolio_mapping_plan.csv",
        [
            {
                "condition": "stressed_panic",
                "portfolio_mapping": "unchanged defensive posture",
                "guardrail": "no offense unlock in stressed_panic",
            },
            {
                "condition": "recovery_fragile",
                "portfolio_mapping": "cautious unless future breadth confirmation is independently strong",
                "guardrail": "fake_recovery_warning blocks re-risking",
            },
            {
                "condition": "neutral_stock_risk_on",
                "portfolio_mapping": "reduce BIL and increase validated ETF offense sleeve",
                "guardrail": "only after PIT stock breadth validation beats ETF breadth same-state lift",
            },
            {
                "condition": "broad_bull",
                "portfolio_mapping": "increase US/sector ETF offense budget",
                "guardrail": "must not become disguised SPY/QQQ beta",
            },
            {
                "condition": "narrow_bull",
                "portfolio_mapping": "avoid over-aggressive QQQ/SPY/sector concentration",
                "guardrail": "keep diversification/cash buffer",
            },
            {
                "condition": "recovery_confirmed_breadth_strong",
                "portfolio_mapping": "re-risk faster into validated offense sleeve",
                "guardrail": "2022/stressed protection remains audited",
            },
        ],
    )
    return {"checklist": checklist, "tests": tests, "classifier": classifier, "aggression": aggression, "mapping": mapping}


def write_phase5b_prompt() -> None:
    PHASE5B_PROMPT.write_text(
        """# Phase 5B Prompt Outline - PIT Stock Breadth Signal Validation And ETF Allocation

Before starting, read CLAUDE.md. Phase 5B uses installed point-in-time stock
breadth data as a signal only; it still trades ETFs.

1. Verify repo state, Phase 5A artifacts, `data/stock_breadth/README.md`, and installed raw PIT stock breadth inputs.
2. Run `python3 scripts/build_pit_stock_breadth_panel.py` and require schema, bias, leakage, and lag checks to pass.
3. Validate stock breadth signal lift versus ETF/sector breadth baselines before any portfolio build.
4. Validate active/inactive and same-state forward returns for SPY, QQQ, GGG1, Phase 2/3/4/4B shadows, and sector sleeves.
5. Build at most five ETF-trading candidates only if stock breadth adds same-state lift beyond ETF breadth.
6. Preserve `stressed_panic`; do not change production pin, official shadow, or GGG1 automatically.
7. Calculate full, 2016+, 2020+, 2021+, 2022 bear, and 2023+ metrics versus GGG1, Phase 2/3/4/4B, production, official shadow, SPY, QQQ, 60/40, and equal-weight benchmarks.
8. Reject or mark research-only if data is current-constituent-only, survivorship-biased, unlagged, missing delisted stocks, or not demonstrably better than ETF breadth.
9. Produce state diagnostics, hidden beta/cash checks, 2022/stress checks, and explicit next-phase recommendation.
""",
        encoding="utf-8",
    )


def build_ingestion_status() -> pd.DataFrame:
    missing_path = METADATA / "missing_inputs_report.csv"
    quality_path = METADATA / "data_quality_report.csv"
    processed_path = PROCESSED / "stock_breadth_weekly.csv"
    rows = [
        {
            "script": "scripts/build_pit_stock_breadth_panel.py",
            "ran_in_phase5a": True,
            "exit_expected": "0 even when raw stock inputs are missing",
            "missing_inputs_report_exists": missing_path.exists(),
            "data_quality_report_exists": quality_path.exists(),
            "processed_weekly_panel_exists": processed_path.exists(),
            "status": "MISSING_INPUTS_REPORTED" if missing_path.exists() and not processed_path.exists() else "CHECK_OUTPUTS",
            "message": "No raw PIT stock files installed; scaffold exited cleanly and wrote missing input report."
            if missing_path.exists() and not processed_path.exists()
            else "Inspect metadata outputs.",
        }
    ]
    return save_csv("phase5a_ingestion_scaffold_status.csv", rows)


def build_report(frames: dict[str, pd.DataFrame]) -> None:
    source_refs = [
        "- Norgate official docs: https://norgatedata.com/data-content-tables.php and https://norgatedata.com/index.php/pricing/",
        "- CRSP official guide: https://www.crsp.org/wp-content/uploads/guides/CRSP10_Year_US_Stock_Database_Guide.pdf",
        "- Sharadar official page: https://www.sharadar.com/",
        "- Nasdaq Data Link help: https://help.data.nasdaq.com/article/508-do-you-cover-delisted-stocks",
        "- Alpha Vantage docs: https://www.alphavantage.co/documentation/",
        "- Polygon/Massive ticker docs: https://polygon.io/docs/rest/stocks/tickers/all-tickers",
        "- S&P DJI S&P 500 page: https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
    ]
    files = sorted(str(path.relative_to(ROOT)) for path in OUT.glob("*"))
    text = f"""# Phase 5A - Point-in-Time Stock Breadth Data Scaffold

**Date:** 2026-05-07
**Type:** Data infrastructure and research-readiness phase. No strategy candidates built.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Official shadow pin:** `improved_phase2b_combo_abc`
**Best aggressive shadow:** `improved_phase4b_refined_sector_20pct`
**Final recommendation:** `NEEDS_DATA_SOURCE_DECISION`

## Commands Executed

```bash
{chr(10).join(COMMANDS_EXECUTED)}
```

## Files Created / Modified

- `scripts/phase_5a_pit_stock_breadth_data_scaffold.py`
- `scripts/build_pit_stock_breadth_panel.py`
- `data/stock_breadth/README.md`
- `data/stock_breadth/metadata/missing_inputs_report.csv`
- `docs/research/2026-05-07_phase_5a_pit_stock_breadth_data_scaffold_report.md`
- `docs/research/project_journey.md`

Output files in `data/research/phase_5a_pit_stock_breadth_data_scaffold/`:

```text
{chr(10).join(files)}
```

## Phase 5 Blocker Summary

Phase 5 correctly stopped because the repo has ETF data and ETF/sector breadth,
but no individual stock price panel, no stock constituent list, and no
point-in-time membership file. Current-constituent breadth would be
survivorship-biased and cannot support promotion.

## Data Requirements

{md_table(frames['requirements'], 10)}

Required schema files were written for index membership, stock prices, stock
metadata, and sector classification.

## Source Option Audit

{md_table(frames['source_audit'], 12)}

## Source References

{chr(10).join(source_refs)}

## Recommended Data Source Path

{md_table(frames['recommended_path'], 8)}

## Local Storage Design

{md_table(frames['storage'], 10)}

## Git Large File Plan

{md_table(frames['git_plan'], 10)}

Large raw stock data should remain local, external, or Git LFS-backed. Phase 5A
did not modify `.gitignore`; it only documented recommended future ignore rules.

## Ingestion Scaffold Status

{md_table(frames['ingestion_status'], 5)}

`scripts/build_pit_stock_breadth_panel.py` defines expected input paths,
schema checks, date/duplicate validation, and causal lagged feature outputs. It
ran successfully and exited 0 because inputs are absent, writing
`data/stock_breadth/metadata/missing_inputs_report.csv`.

## Bias And Leakage Checklist

{md_table(frames['checklist'], 20)}

## Future Acceptance Tests

{md_table(frames['tests'], 12)}

## Market-State Classifier Redesign Plan

{md_table(frames['classifier'], 10)}

## Aggression Score Design

{md_table(frames['aggression'], 10)}

## Future Portfolio Mapping Plan

{md_table(frames['mapping'], 10)}

## Phase 5B Prompt Outline

See `data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_phase5b_prompt_outline.md`.

## Final Recommendation

`NEEDS_DATA_SOURCE_DECISION`

Exact next human action: choose and provision one point-in-time stock data path:
Norgate Platinum/Diamond, CRSP/Compustat via WRDS, or a verified Sharadar/Nasdaq
Data Link path with PIT membership and delisted-stock coverage. After the data
source is installed under `data/stock_breadth/raw/`, run
`python3 scripts/build_pit_stock_breadth_panel.py` and proceed to Phase 5B only
if bias/leakage checks pass.

## Resume / Project Story Summary

Phase 5A turned the Phase 5 blocker into a concrete data plan and scaffold. It
did not build strategy candidates, did not trade stocks, did not change pins,
and did not download stock panels. The path forward is a data-source decision
and installation step before any new stock-breadth classifier or ETF allocation
research.
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    print("=== Phase 5A - PIT Stock Breadth Data Scaffold ===")
    req_frames = build_requirements()
    source_frames = build_source_audit()
    storage_frames = build_storage_plan()
    plan_frames = build_validation_and_classifier_plan()
    write_phase5b_prompt()
    ingestion_status = build_ingestion_status()

    protocol = {
        "phase": "phase_5a_pit_stock_breadth_data_scaffold",
        "date": "2026-05-07",
        "final_recommendation": "NEEDS_DATA_SOURCE_DECISION",
        "portfolio_candidates_built": False,
        "production_pin_changed": False,
        "official_shadow_pin_changed": False,
        "individual_stock_trading_added": False,
        "stock_data_downloaded": False,
        "current_constituents_used_as_historical_truth": False,
        "build_improvement_artifacts_modified": False,
    }
    (OUT / "phase5a_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    frames = {
        "requirements": req_frames["requirements"],
        "source_audit": source_frames["audit"],
        "recommended_path": source_frames["recommended_path"],
        "storage": storage_frames["storage"],
        "git_plan": storage_frames["git_plan"],
        "ingestion_status": ingestion_status,
        **plan_frames,
    }
    build_report(frames)
    print(f"Output directory: {OUT}")
    print(f"Stock breadth README: {README}")
    print(f"Report: {REPORT}")
    print("Recommendation: NEEDS_DATA_SOURCE_DECISION")
    print("Done. No candidates built and no pins changed.")


if __name__ == "__main__":
    main()
