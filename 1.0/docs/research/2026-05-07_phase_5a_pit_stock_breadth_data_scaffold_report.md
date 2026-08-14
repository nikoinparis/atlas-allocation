# Phase 5A - Point-in-Time Stock Breadth Data Scaffold

**Date:** 2026-05-07
**Type:** Data infrastructure and research-readiness phase. No strategy candidates built.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Official shadow pin:** `improved_phase2b_combo_abc`
**Best aggressive shadow:** `improved_phase4b_refined_sector_20pct`
**Final recommendation:** `NEEDS_DATA_SOURCE_DECISION`

## Commands Executed

```bash
pwd
git status --short
git branch --show-current
git worktree list
find .. -name CLAUDE.md -maxdepth 3
sed -n '1,260p' CLAUDE.md
test -f docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md && test -d data/research/phase_5_true_stock_breadth_data_upgrade && test -f data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv
sed -n '1,240p' docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md
find data/research/phase_5_true_stock_breadth_data_upgrade -maxdepth 1 -type f | sort
python3 - <<'PY'  # small pandas summaries of phase5_data_gap_report.csv, phase5_stock_breadth_source_audit.csv, phase5_survivorship_bias_risk_register.csv, phase5_next_phase_decision.csv
find data/01_data_hub -maxdepth 2 -type f | sort | head -n 120
find data/04_layer2b_risk_regime_engine -maxdepth 2 -type f | sort | head -n 120
sed -n '1,260p' .gitignore
rg -n "yfinance|yf\.download|download|weekly_prices|daily_prices|parquet|to_parquet|read_parquet|data/01_data_hub|public/dashboard-data" scripts notebooks data docs -g '!data/research/phase_ooo_signal_discovery/**' -g '!data/research/phase_ppp_latent_factor_discovery/**' -g '!data/research/phase_qqq_deep_feature_interaction_mining/**' -g '!data/research/phase_sss*/**'
web source checks for Norgate, CRSP, Nasdaq Data Link/Sharadar, Alpha Vantage, Polygon, S&P DJI
python3 -m py_compile scripts/build_pit_stock_breadth_panel.py scripts/phase_5a_pit_stock_breadth_data_scaffold.py
python3 scripts/build_pit_stock_breadth_panel.py
python3 scripts/phase_5a_pit_stock_breadth_data_scaffold.py
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
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_aggression_score_design.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_bias_leakage_validation_checklist.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_data_source_option_audit.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_future_acceptance_tests.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_future_portfolio_mapping_plan.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_git_large_file_plan.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_ingestion_scaffold_status.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_local_storage_plan.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_market_state_classifier_redesign_plan.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_phase5b_prompt_outline.md
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_pit_data_requirements.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_protocol.json
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_recommended_data_source_path.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_required_schema_index_membership.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_required_schema_sector_classification.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_required_schema_stock_metadata.csv
data/research/phase_5a_pit_stock_breadth_data_scaffold/phase5a_required_schema_stock_prices.csv
```

## Phase 5 Blocker Summary

Phase 5 correctly stopped because the repo has ETF data and ETF/sector breadth,
but no individual stock price panel, no stock constituent list, and no
point-in-time membership file. Current-constituent breadth would be
survivorship-biased and cannot support promotion.

## Data Requirements

```
                         dataset          priority                                                                      preferred_scope                                                                                       minimum_fields                                                                                                                      causal_requirement                                                       bias_risk_if_missing                                                                 phase5b_use
  point_in_time_index_membership          REQUIRED                                            S&P 500 full history; Nasdaq-100 optional                  security_id,ticker,index_name,membership_start,membership_end,effective_date,source membership row can only affect breadth on/after effective date, lagged at least one rebalance period if publication timing is uncertain HIGH: current-constituent backfill creates survivorship and lookahead bias              define active members for each week before calculating breadth
           adjusted_stock_prices          REQUIRED                  daily adjusted close for all active and delisted historical members    date,security_id,ticker,adjusted_close,close,volume,split_factor,dividend_amount,delisting_return                                                     weekly features use prices available through week t; signals use lagged t+1 columns          HIGH: omitting dead/delisted stocks overstates historical breadth moving-average, momentum, high, drawdown, and equal-weight breadth features
ticker_security_identity_mapping          REQUIRED                            permanent id such as PERMNO/vendor id with ticker history security_id,permanent_id_source,ticker,name,exchange,first_trade_date,last_trade_date,delisting_date                                                         ticker changes must map to the same security without retroactive symbol leakage  HIGH: ticker-only joins break on mergers, ticker reuse, and class changes        stable joins among membership, prices, sector, and delisting records
           sector_classification         PREFERRED                                           point-in-time GICS sector/industry history     security_id,sector,industry,classification_start,classification_end,classification_system,source                                                                      classification active for week t only if known/effective by week t            MEDIUM: static sectors are acceptable only with research caveat            sector-level stock breadth and broad-vs-narrow leadership checks
 publication_and_lag_assumptions REQUIRED_METADATA source manifest with update schedule, timezone, publication lag, and revision policy             source_name,download_date,coverage_start,coverage_end,publication_lag_rule,license_notes                                            apply at least 1-week signal lag; membership uncertainty should add one rebalance-period lag        MEDIUM/HIGH: unclear publication timing can create silent lookahead                 document why each feature is tradable at the next rebalance
```

Required schema files were written for index membership, stock prices, stock
metadata, and sector classification.

## Source Option Audit

```
                                                               source  available_now_in_repo                                     point_in_time_membership                                                       delisted_stock_coverage                                                         adjusted_prices                                                   sector_classification                                                           ticker_history_or_perm_id                                                               expected_bias_risk                                                                                              cost_or_access_notes implementation_complexity                                              production_decision_safe                                      research_only_safe                                                                         recommended_role                                                                                                verification_status                                                                                       reference_url
                                             Existing local repo data                   True                                                        False                                                                         False                                                                   False                                                                   False                                                                               False                                                       UNUSABLE_FOR_STOCK_BREADTH                                                    Already inspected; only ETF data and ETF/sector breadth exist.                      none                                                                 False                                                   False                                                       Do not use for true stock breadth.                                                                                                   verified locally                                                                                                    
                              Norgate Data US Stocks Platinum/Diamond                  False                                                         True                                                                          True                                                                    True                                               needs manual verification vendor symbol plus delisted suffix; permanent-id behavior needs manual verification         LOW if index constituent plugin and delisted database are used correctly Paid subscription; official pages say delisted stocks and historical constituent access require Platinum/Diamond.                    medium                              Yes after license, schema, and lag audit                                                    True                             Most practical non-institutional path if user can subscribe.                                  official docs checked; details still require manual subscription/API verification         https://norgatedata.com/data-content-tables.php; https://norgatedata.com/index.php/pricing/
                                            CRSP / Compustat via WRDS                  False needs manual verification for chosen index constituent table                                                                          True                                                                    True available through Compustat/GICS if licensed; needs manual verification                                                                                True LOW if PERMNO/PERMCO, delisting returns, and PIT membership are joined correctly                                                                   Institutional/academic access usually required.                      high                              Yes after access and reproducible export                                                    True                              Highest-quality institutional path if user has WRDS access.              CRSP guide checked for PERMNO and delisting fields; index membership access needs manual verification              https://www.crsp.org/wp-content/uploads/guides/CRSP10_Year_US_Stock_Database_Guide.pdf
                                          Nasdaq Data Link / Sharadar                  False                                    needs manual verification                                                                          True                                                                    True                                               needs manual verification                                                           needs manual verification          LOW/MEDIUM depending on PIT constituent availability and ticker mapping                           Paid vendor feeds; official pages indicate Sharadar has active/delisted stock coverage.               medium/high         Only if PIT membership and delisting methodology are verified                                                    True   Candidate path if it can provide historical index membership or a safe proxy universe.                                          official docs checked; PIT constituent specifics need manual verification    https://www.sharadar.com/; https://help.data.nasdaq.com/article/508-do-you-cover-delisted-stocks
Polygon / Tiingo / Alpha Vantage / yfinance with current constituents                  False                                                        False partial/varies by vendor; not enough for index PIT breadth without membership varies; Alpha Vantage and Polygon expose adjusted price endpoints/flags                                                        varies or absent                                                   varies; needs manual verification                                         HIGH if paired with today's constituents                               Can be cheap and API-friendly, but not sufficient for promotable PIT index breadth.                    medium                                                                 False Diagnostic only with explicit SURVIVORSHIP_BIASED label Do not use for production decisions; optional tiny diagnostic after PIT path is decided. official docs checked for Alpha Vantage listing status and Polygon ticker active flag; PIT index membership absent https://www.alphavantage.co/documentation/; https://polygon.io/docs/rest/stocks/tickers/all-tickers
                                 Wikipedia/current index constituents                  False                                                        False                                                                         False                                                                   False                                                     current/static only                                                                               False                                                                             HIGH               Free current constituent list and partial changes table, but not a validated PIT stock data system.                       low                                                                 False                                         Diagnostic only                                 Use only for UI/schema dry runs, never historical truth.                                                                                  needs manual verification if used                                           https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
                                               Vendor breadth indexes                  False                                  not exposed at member level                                                 depends on vendor methodology                                   not applicable if breadth series only                                                depends on vendor series                                                                               False                LOW/MEDIUM if methodology and historical revisions are documented                                         May be easier than full stock panel but less auditable and less flexible.                low/medium Only after methodology, revisions, and publication lag are documented                                                    True           Secondary option for classifier features if member-level panel is unavailable.                                                                                   needs manual vendor verification                                                                                                    
                   Manual small diagnostic current-constituent sample                  False                                                        False                                                                         False                                  could be fetched but not in this phase                                                     current/static only                                                                               False                                                                             HIGH                                                                                         Cheap but non-promotable.                       low                                                                 False                                         Diagnostic only                              Use only to test code mechanics after scaffold is accepted.                                                                                                           not used                                                                                                    
```

## Source References

- Norgate official docs: https://norgatedata.com/data-content-tables.php and https://norgatedata.com/index.php/pricing/
- CRSP official guide: https://www.crsp.org/wp-content/uploads/guides/CRSP10_Year_US_Stock_Database_Guide.pdf
- Sharadar official page: https://www.sharadar.com/
- Nasdaq Data Link help: https://help.data.nasdaq.com/article/508-do-you-cover-delisted-stocks
- Alpha Vantage docs: https://www.alphavantage.co/documentation/
- Polygon/Massive ticker docs: https://polygon.io/docs/rest/stocks/tickers/all-tickers
- S&P DJI S&P 500 page: https://www.spglobal.com/spdji/en/indices/equity/sp-500/

## Recommended Data Source Path

```
 rank                                    path                                                               when_to_choose                                                                                                             why                                                                                                               blocking_manual_checks
    1 Norgate Data US Stocks Platinum/Diamond            User wants a practical desktop/vendor workflow and can subscribe.  Combines historical daily data, delisted stock coverage, and historical constituent access in one vendor path. Confirm Python/export access, schema fields, sector support, license, and how historical constituent plugin exposes effective dates.
    2               CRSP / Compustat via WRDS                               User has university/institutional WRDS access.                  Best institutional identity/delisting framework via PERMNO/PERMCO and delisting return fields.                                                             Confirm PIT S&P 500/Nasdaq constituent table access and export workflow.
    3               Sharadar/Nasdaq Data Link User already has Sharadar/Nasdaq subscription and can verify PIT membership. Active/delisted stock coverage appears promising, but constituent membership must be verified before promotion.                              Confirm historical index membership, delisting returns/adjustments, ticker mapping, and sector history.
    4  Current constituents plus yfinance/API                                              Only for code-path smoke tests.                                                                         Survivorship-biased and not promotable.                                                                          Must label all outputs SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY.
```

## Local Storage Design

```
                                                                      path                                                                purpose                                      format                                                     commit_policy
                           data/stock_breadth/raw/index_membership.parquet                                PIT S&P 500/Nasdaq membership intervals parquet preferred; csv accepted by scaffold    avoid committing if large; commit only small samples/manifests
data/stock_breadth/raw/stock_prices_daily.parquet or partitioned directory daily adjusted stock prices for active and delisted historical members               partitioned parquet preferred keep local/external/LFS; do not normal-git commit large raw panel
                                data/stock_breadth/raw/security_master.csv                             stable identity mapping and ticker history                     csv acceptable if small                   can commit if license permits and file is small
                          data/stock_breadth/raw/sector_classification.csv                                   sector/GICS classification intervals                              csv or parquet                   can commit if license permits and file is small
                     data/stock_breadth/processed/stock_breadth_weekly.csv                                 weekly aggregate stock breadth signals                                         csv                       commit only after size and bias checks pass
                     data/stock_breadth/metadata/missing_inputs_report.csv                               safe scaffold status when data is absent                                         csv                                                    safe to commit
```

## Git Large File Plan

```
                           item                              risk                                                                           recommendation                                     gitignore_change
    raw daily stock price panel   likely over GitHub 100 MB limit store outside git, partition parquet locally, or use Git LFS if repository policy allows recommend only; do not modify .gitignore in Phase 5A
 processed weekly breadth panel  probably small if aggregate-only            check size before committing; keep member-level wide panels out of normal git                                             none now
metadata and validation reports                             small                                                        safe to commit if license permits                                                 none
current-constituent diagnostics bias and possible large downloads                                          avoid unless explicitly labeled diagnostic-only                           keep raw diagnostics local
```

Large raw stock data should remain local, external, or Git LFS-backed. Phase 5A
did not modify `.gitignore`; it only documented recommended future ignore rules.

## Ingestion Scaffold Status

```
                                  script  ran_in_phase5a                            exit_expected  missing_inputs_report_exists  data_quality_report_exists  processed_weekly_panel_exists                  status                                                                                   message
scripts/build_pit_stock_breadth_panel.py            True 0 even when raw stock inputs are missing                          True                       False                          False MISSING_INPUTS_REPORTED No raw PIT stock files installed; scaffold exited cleanly and wrote missing input report.
```

`scripts/build_pit_stock_breadth_panel.py` defines expected input paths,
schema checks, date/duplicate validation, and causal lagged feature outputs. It
ran successfully and exited 0 because inputs are absent, writing
`data/stock_breadth/metadata/missing_inputs_report.csv`.

## Bias And Leakage Checklist

```
                          check_id  required_for_phase5b                                                                                          description                                           failure_action
     point_in_time_membership_only                  True Membership rows include effective start/end dates and active members are selected as of week t only. block production/shadow promotion; research-only at most
   no_current_constituent_backfill                  True                                     No current S&P 500/Nasdaq list is used as a historical universe. block production/shadow promotion; research-only at most
    no_future_membership_additions                  True            A future addition cannot enter active membership before its effective date plus lag rule. block production/shadow promotion; research-only at most
        no_delisted_stock_omission                  True             Delisted/dead members are represented or omission is explicitly blocking production use. block production/shadow promotion; research-only at most
       price_adjustment_documented                  True                                            Split/dividend/delisting adjustment method is documented. block production/shadow promotion; research-only at most
             ticker_changes_mapped                  True                                                       Ticker changes map through stable security id. block production/shadow promotion; research-only at most
    duplicate_security_ids_handled                  True                        Duplicate ticker/security/date rows are absent or resolved deterministically. block production/shadow promotion; research-only at most
sector_classifications_timestamped                  True                                    Sector intervals are PIT or static caveat is explicitly recorded. block production/shadow promotion; research-only at most
                signal_lag_applied                  True                                          All features have lag1w columns used for portfolio signals. block production/shadow promotion; research-only at most
       no_centered_rolling_windows                  True                                                          All rolling calculations are trailing only. block production/shadow promotion; research-only at most
     no_future_returns_in_features                  True                                   Forward returns appear only in validation outputs, never features. block production/shadow promotion; research-only at most
        no_random_train_test_split                  True                                                                          Validation is time ordered. block production/shadow promotion; research-only at most
                  coverage_by_week                  True                                         Active member count and price coverage are reported by week. block production/shadow promotion; research-only at most
        missing_price_rate_by_week                  True                                 Weekly missing price rate is below acceptance threshold or caveated. block production/shadow promotion; research-only at most
           delisting_count_by_year                  True                                         Delisting count by year is reconciled if vendor supplies it. block production/shadow promotion; research-only at most
        membership_turnover_sanity                  True                                         Additions/removals by year are plausible and source-aligned. block production/shadow promotion; research-only at most
      compare_stock_vs_etf_breadth                  True                                            Stock breadth is compared to Phase 4B ETF/sector breadth. block production/shadow promotion; research-only at most
     compare_index_vs_equal_weight                  True                                        Broad index return is compared to equal-weight member return. block production/shadow promotion; research-only at most
```

## Future Acceptance Tests

```
                     test_id               scope                                                                          acceptance_rule
    missing_inputs_exit_zero  ingestion scaffold  script exits 0 and writes metadata/missing_inputs_report.csv when raw inputs are absent
     schema_required_columns      all raw tables                                 all required schema columns present before feature build
       membership_date_order    index membership                          membership_start exists and membership_end is blank or >= start
   duplicate_membership_rows    index membership                                               no duplicate security/index/start/end rows
  weekly_active_member_count         built panel active member count is plausible by week and not a constant current-constituent backfill
           lag_columns_exist         built panel                                      all signal fields have explicit *_lag1w equivalents
no_phase5b_without_bias_pass research governance               candidate builds are blocked until source, bias, and alignment checks pass
```

## Market-State Classifier Redesign Plan

```
    classifier_area                                                                                  future_labels                                                                        stock_breadth_inputs                                               intended_effect                                      states_unchanged
neutral_mixed_split          neutral_stock_risk_on | neutral_chop | neutral_deteriorating | neutral_recovery_setup                    pct above 200d, positive 13w/26w returns, breadth thrust, narrow warning    reduce unnecessary BIL only in broad neutral risk-on weeks                      stressed_panic remains unchanged
       bull_quality                    broad_bull | narrow_bull | defensive_bull | late_cycle_bull | fake_recovery stock breadth level, sector breadth, index-vs-equal-weight divergence, defensive leadership distinguish strong broad bull from QQQ/SPY-only narrow market                      stressed_panic remains unchanged
    recovery_rerisk recovery_confirmed_breadth_strong | recovery_confirmed_breadth_weak | recovery_fragile_fakeout                  breadth thrust 4w/8w, percentage above MA, active member count improvement     re-risk faster only when recovery has broad participation recovery_fragile cautious unless separately confirmed
```

## Aggression Score Design

```
               component  weight                                                                 inputs                                            interpretation
           breadth_level    0.30 pct_members_above_200d_ma_lag1w, pct_members_positive_26w_return_lag1w          higher when broad market participation is strong
          breadth_thrust    0.20                       breadth_thrust_4w_lag1w, breadth_thrust_8w_lag1w                    higher when participation is improving
     sector_confirmation    0.15 sector-level breadth dispersion and number of sectors above thresholds blocks narrow single-sector leadership from looking broad
  volatility_containment    0.15                                existing VIX/regime volatility features           reduces aggression when market risk is elevated
credit_and_risk_appetite    0.10                            existing canary/credit ETF breadth features                       requires risk appetite confirmation
         state_stability    0.10    weeks since state transition and no recovery_fragile/stressed_panic                            penalizes unstable transitions
```

## Future Portfolio Mapping Plan

```
                        condition                                                   portfolio_mapping                                                                 guardrail
                   stressed_panic                                         unchanged defensive posture                                       no offense unlock in stressed_panic
                 recovery_fragile cautious unless future breadth confirmation is independently strong                                   fake_recovery_warning blocks re-risking
            neutral_stock_risk_on                reduce BIL and increase validated ETF offense sleeve only after PIT stock breadth validation beats ETF breadth same-state lift
                       broad_bull                               increase US/sector ETF offense budget                                    must not become disguised SPY/QQQ beta
                      narrow_bull                  avoid over-aggressive QQQ/SPY/sector concentration                                          keep diversification/cash buffer
recovery_confirmed_breadth_strong                        re-risk faster into validated offense sleeve                                  2022/stressed protection remains audited
```

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
