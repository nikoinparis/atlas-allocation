# Phase 5 - True Stock Breadth Data Upgrade

**Date:** 2026-05-07
**Type:** Data + strategy research gate. No portfolio candidate was built.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Official shadow pin:** `improved_phase2b_combo_abc`
**Base:** `improved_phaseggg_confirmed_only_robust_offense`
**Phase 4B best:** `improved_phase4b_refined_sector_20pct`

## Commands Executed

```
pwd
git status --short
git branch --show-current
git worktree list
find .. -name CLAUDE.md -maxdepth 3
sed -n '1,240p' CLAUDE.md
test -f docs/research/2026-05-07_phase_1_return_unlock_audit_report.md
test -f docs/research/2026-05-07_phase_2_aggressive_etf_variant_report.md
test -f docs/research/2026-05-07_phase_3_breadth_confirmed_us_offense_report.md
test -f docs/research/2026-05-07_phase_4_sector_breadth_rotation_report.md
test -f docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md
test -f data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv
test -f data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4b_refined_sector_20pct.csv
test -d data/research/phase_4b_refined_sector_rotation
rg -n 'neutral_mixed|stressed_panic|Decision|recommendation|Phase 4B' docs/research/2026-05-07_phase_*_report.md
find data/01_data_hub data/02_layer1_signals data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction -maxdepth 2 -type f | head -n 200
rg -n 'yfinance|constituent|stock|holdings|point-in-time|breadth' scripts data docs
python3 -m py_compile scripts/phase_5_true_stock_breadth_data_upgrade.py
python3 scripts/phase_5_true_stock_breadth_data_upgrade.py
find data/research/phase_5_true_stock_breadth_data_upgrade -maxdepth 1 -type f | sort
find data/research/phase_5_true_stock_breadth_data_upgrade -maxdepth 1 -type f | wc -l
python3 - <<'PY'
import pandas as pd
from pathlib import Path
out=Path('data/research/phase_5_true_stock_breadth_data_upgrade')
for name in ['phase5_etf_universe_inventory.csv','phase5_stock_data_inventory.csv','phase5_data_gap_report.csv','phase5_stock_breadth_source_audit.csv','phase5_selection_table.csv','phase5_next_phase_decision.csv']:
    df=pd.read_csv(out/name)
    print(name, df.shape)
    print(df.head(10).to_string(index=False))
PY
tail -n 220 docs/research/project_journey.md
wc -l docs/research/project_journey.md docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md scripts/phase_5_true_stock_breadth_data_upgrade.py
```

## Files Created / Modified

**Script created:** `scripts/phase_5_true_stock_breadth_data_upgrade.py`

**Output directory:** `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_5_true_stock_breadth_data_upgrade`

**Report created:** `docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md`

**Project journey updated:** `docs/research/project_journey.md`

**Build script:** not modified; no Phase 5 portfolio candidates were allowed because no clean stock-breadth source exists locally.

## Phase 1-4B Bottleneck Summary

Phase 1 identified the return ceiling as mandate-driven, especially BIL/cash drag in neutral_mixed and defense drag in calm_trend, while stressed_panic protection worked and should not be weakened.

Phase 2 showed that moving capital into existing offense sleeves was insufficient because those sleeves did not capture US bull-market upside.

Phase 3 improved Sharpe by switching a small offense component to US equity in high-breadth calm states, but the component was too small to move full-period return enough.

Phase 4 and 4B added/refined a larger sector ETF offense sleeve. Phase 4B best reached about 7.76% return and 0.959 Sharpe, but still did not approach the 8.5-9% target.

## ETF Universe Inventory

```
                                 item  value                                                                                                                      evidence
     total_etfs_in_weekly_return_data     35                                                                     data/01_data_hub/weekly_prices.csv columns excluding Date
                          equity_etfs     20                                                                           universe_metadata.csv asset_class in Equities/REITs
                          sector_etfs     10                                                                                       XLV,XLU,XLP,XLK,XLI,XLF,XLE,XLB,VNQ,XLY
defensive_cash_bond_commodity_fx_etfs     15                                                                     universe_metadata.csv asset_class in Bonds/Commodities/FX
         full_coverage_2005_2026_etfs     26                       TIP,SPY,XLV,XLU,XLP,XLK,XLI,XLF,XLE,XLB,VUG,VTV,VNQ,TLT,XLY,IEF,EEM,QQQ,EFA,EWJ,GLD,LQD,SHY,IWM,IAU,VWO
  liquid_tradable_current_system_etfs     34                                                                              Completeness >=80% and >=900 weekly observations
         individual_stock_price_files      0                        No local stock price panel found outside .venv/.claude; daily/weekly panels contain ETF universe only.
              stock_constituent_lists      0 No usable local S&P 500/Nasdaq constituent list found; holdings artifacts are portfolio/ETF diagnostics, not stock universes.
    point_in_time_universe_membership      0                                                                                 No point-in-time stock membership file found.
                  prior_breadth_files     35                                                               Existing breadth is ETF/sector breadth, not true stock breadth.
```

```
ticker asset_class                 bucket start_date   end_date  completeness_pct  has_full_2005_2026_history  liquid_tradable_current_system
   BIL       Bonds cash_or_short_duration 2007-06-01 2026-04-10              88.7                       False                            True
   SHY       Bonds cash_or_short_duration 2005-01-07 2026-04-10             100.0                        True                            True
   DBA Commodities    commodity_or_fx_etf 2007-01-05 2026-04-10              90.6                       False                            True
   GLD Commodities    commodity_or_fx_etf 2005-01-07 2026-04-10             100.0                        True                            True
   IAU Commodities    commodity_or_fx_etf 2005-01-28 2026-04-10              99.7                        True                            True
  PDBC Commodities    commodity_or_fx_etf 2014-11-07 2026-04-10              53.8                       False                           False
   SLV Commodities    commodity_or_fx_etf 2006-04-28 2026-04-10              93.9                       False                            True
   USO Commodities    commodity_or_fx_etf 2006-04-14 2026-04-10              94.1                       False                            True
   UUP          FX    commodity_or_fx_etf 2007-03-02 2026-04-10              89.9                       False                            True
   HYG       Bonds     defensive_bond_etf 2007-04-13 2026-04-10              89.4                       False                            True
   IEF       Bonds     defensive_bond_etf 2005-01-07 2026-04-10             100.0                        True                            True
   LQD       Bonds     defensive_bond_etf 2005-01-07 2026-04-10             100.0                        True                            True
   MBB       Bonds     defensive_bond_etf 2007-03-16 2026-04-10              89.7                       False                            True
   TIP       Bonds     defensive_bond_etf 2005-01-07 2026-04-10             100.0                        True                            True
   TLT       Bonds     defensive_bond_etf 2005-01-07 2026-04-10             100.0                        True                            True
   EEM    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   EFA    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   EWJ    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   IWM    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   QQQ    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   SPY    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   VEA    Equities             equity_etf 2007-07-27 2026-04-10              88.0                       False                            True
   VTV    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   VUG    Equities             equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   VWO    Equities             equity_etf 2005-03-11 2026-04-10              99.2                        True                            True
   VNQ       REITs      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLB    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLE    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLF    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLI    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLK    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLP    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLU    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLV    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
   XLY    Equities      sector_equity_etf 2005-01-07 2026-04-10             100.0                        True                            True
```

## Stock Data Inventory

No local individual-stock price panel, stock constituent list, or point-in-time universe membership was found outside the existing ETF/research artifacts.

```
                                                                                                                         path                          data_type                                        usable_for_phase5                survivorship_bias_risk
                                                                       data/02_layer1_signals/signal_breadth_confirmation.csv etf_breadth_or_prior_phase_breadth        ETF breadth baseline only; not true stock breadth LOW_ETF_BREADTH_BUT_NOT_STOCK_BREADTH
                                             data/03_layer2a_strategy_logic/strategy_positions_composite_breadth_filtered.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
                                               data/03_layer2a_strategy_logic/strategy_returns_composite_breadth_filtered.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
                data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_conditional_prod_r2_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod70_r2_30_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod70_r3_30_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod80_r2_20_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod80_r3_20_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod90_r2_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                       data/05_layer3_portfolio_construction/phase_u_controls_improved_phaseu_prod90_r3_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                                                       data/05_layer3_portfolio_construction/phase_u_holdings_diagnostics.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                   data/05_layer3_portfolio_construction/phase_v_controls_improved_phasev_conditional95_80_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                   data/05_layer3_portfolio_construction/phase_v_controls_improved_phasev_prod90_phasen_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                   data/05_layer3_portfolio_construction/phase_v_controls_improved_phasev_prod90_phaseo_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
                                                       data/05_layer3_portfolio_construction/phase_v_holdings_diagnostics.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_balanced_breadth_aggressive.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
           data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_breadth_credit_risk_on_offense.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_breadth_neutral_cash_unlock.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
             data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_high_breadth_calm_us_offense.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
               data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_stretch_breadth_aggressive.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
                  data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase4_balanced_sector_breadth.csv       other_breadth_named_artifact                                   not true stock breadth               UNKNOWN_OR_NOT_RELEVANT
             data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseaa_prod90_z1_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
             data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseaa_prod95_z1_05_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseaa_state_conditional_prod_z1_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
       data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_conditional_prod_r2_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_prod70_r2_30_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_prod70_r3_30_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_prod80_r2_20_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_prod80_r3_20_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
              data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseu_prod90_r2_10_holdings_blend.csv portfolio_or_etf_holdings_artifact not individual-stock breadth; portfolio diagnostics only                    NOT_STOCK_UNIVERSE
```

## Stock Breadth Source Audit

```
                                        source_option  available_now                                     survivorship_bias_risk  point_in_time_safe  can_be_used_for_research_only  can_be_used_for_production_decision                                                                                                  recommended_use
                            Existing repo stock files          False                                         N/A because absent               False                          False                                False                                   Do not build stock breadth; no local stock price/PIT membership source exists.
          Existing yfinance/data-hub download pattern           True                   HIGH if paired with today's constituents               False                           True                                False Use only for explicitly labeled current-constituent diagnostics after a universe list is supplied; no promotion.
                  Current S&P 500/Nasdaq constituents          False                                                       HIGH               False                           True                                False          Allowed only as SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY; not used in this run because no local list exists.
Point-in-time constituents plus adjusted stock prices          False        LOW if delistings and membership dates are included                True                           True                                 True                                                                             Preferred Phase 5 data upgrade path.
                          ETF/sector breadth fallback           True              LOW for ETF panels but not true stock breadth                True                           True                                 True                                                     Use as comparison baseline only; Phase 4B already tested it.
                        External clean breadth series          False LOW if vendor supplies historical constituents methodology                True                           True                                 True                                       Acceptable if methodology, revisions, and lag availability are documented.
```

## Survivorship-Bias Risk Register

```
                                 risk                           severity                                                                                                                                    description                                                                        mitigation
current_constituent_survivorship_bias                               HIGH Today's index members exclude historical bankruptcies, delistings, removals, and weak firms, overstating historical breadth and trend quality.    Require PIT membership and delisting-aware prices before production decisions.
           lookahead_membership_dates                               HIGH                                                          Using future constituent additions/removals to define past breadth leaks information.             For each week, include only stocks that were members as of that week.
            delisting_return_omission                               HIGH                                                                        Ignoring delisted stocks removes adverse outcomes and inflates breadth.              Use a source with delisting returns or explicit dead-stock coverage.
   vendor_revision_or_publication_lag                             MEDIUM                                                                        Constituent data may be known only after announcements/effective dates. Use effective dates and lag signal availability by at least one rebalance period.
             ETF_breadth_substitution LOW_FOR_BIAS_HIGH_FOR_SIGNAL_LIMIT                                                     ETF breadth is clean and available, but too coarse to answer true stock breadth questions.                  Keep as baseline, not as a substitute for Phase 5 stock breadth.
```

## Stock Breadth Panel Construction

Panel status: `NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP`.

No stock breadth panel was built. Current-constituent stock breadth would be survivorship-biased diagnostic-only and was not fetched in this run.

## Market-State Classifier Audit

```
                                                                   question                                                                                                                                                              answer                                                 phase5_action
                              Is stressed_panic classification good enough? Yes, based on prior phases and Phase 5 audit. Stressed_panic remains the state that should stay protected; 2022 bear protection was the strategy's validation case.                                 Do not weaken stressed_panic.
                                Are calm_trend weeks truly safe/aggressive?             Broadly safe, but existing ETF breadth is too coarse. Phase 3/4/4B show calm participation can help, but calm_trend still contains quality differences.    Needs true stock breadth for broad-vs-narrow confirmation.
                                                Is neutral_mixed too broad?                             Yes. Neutral_mixed contains high-return risk-on weeks and chop/deteriorating weeks. This is the largest potential classification split. Needs PIT stock breadth to split neutral risk-on versus chop.
Can stock breadth split neutral_mixed into risk-on vs choppy/deteriorating?                                            Not with current repo data. ETF breadth suggests the split is important, but true stock breadth cannot be built locally.          Proceed to point-in-time stock breadth data upgrade.
                   Can stock breadth distinguish broad bull vs narrow bull?                   Conceptually yes, but not implementable with current data. ETF/sector breadth proxies are the safer fallback and were already tested in Phase 4B.     Acquire stock-level breadth before rebuilding classifier.
                                Can stock breadth identify fake recoveries?                                              No local stock data to test. Existing recovery diagnostics can only use ETF breadth improvement and state persistence.          Use PIT stock breadth to validate recovery re-entry.
                      Does breadth improve re-risking after stressed_panic?                                                       ETF breadth gives some signal, but true stock breadth is required to avoid overfitting to ETF proxy behavior. Do not build Phase 5 portfolio candidates without stock data.
               Does breadth explain why sector rotation only partly helped?                                                      Likely. Sector ETF breadth improved timing but is coarse and cannot see underneath sector/index concentration.            True stock breadth is the next information source.
                                        Which states should stay unchanged?                                                          stressed_panic should stay unchanged; recovery_fragile should remain cautious unless separately confirmed.                No portfolio build; no stressed_panic changes.
                                Which states need finer sub-classification?                                                         neutral_mixed first, then calm_trend broad-vs-narrow bull quality, then recovery_confirmed re-risk quality.              Use PIT stock breadth as classifier feature set.
```

## Neutral Mixed ETF-Breadth Fallback Diagnostics

These are comparison baselines, not stock-breadth evidence.

```
                                     split   bucket asset_or_portfolio  n_weeks  ann_return  ann_vol    sharpe  max_drawdown
ETF breadth risk-on split in neutral_mixed   active                SPY      149    0.317230 0.125455  2.528631     -0.082647
ETF breadth risk-on split in neutral_mixed   active                QQQ      149    0.358749 0.165177  2.171910     -0.092344
ETF breadth risk-on split in neutral_mixed   active               ggg1      149    0.135060 0.085998  1.570514     -0.064521
ETF breadth risk-on split in neutral_mixed   active       phase4b_best      149    0.160561 0.092491  1.735966     -0.075166
ETF breadth risk-on split in neutral_mixed inactive                SPY      344   -0.000833 0.152067 -0.005479     -0.292791
ETF breadth risk-on split in neutral_mixed inactive                QQQ      344   -0.001363 0.178658 -0.007628     -0.366702
ETF breadth risk-on split in neutral_mixed inactive               ggg1      344    0.102317 0.072412  1.412980     -0.070075
ETF breadth risk-on split in neutral_mixed inactive       phase4b_best      344    0.103913 0.076905  1.351178     -0.068213
```

## Recovery Rerisk ETF-Breadth Fallback Diagnostics

```
                                           split bucket asset_or_portfolio  n_weeks  ann_return  ann_vol   sharpe  max_drawdown
ETF breadth improvement split in recovery states active                SPY       93    0.472050 0.103798 4.547760     -0.053073
ETF breadth improvement split in recovery states active                QQQ       93    0.742159 0.146412 5.068975     -0.087718
ETF breadth improvement split in recovery states active               ggg1       93    0.047089 0.066261 0.710656     -0.058336
ETF breadth improvement split in recovery states active       phase4b_best       93    0.061165 0.068687 0.890494     -0.055966
```

## Stock Breadth Signal Definitions

```
                            signal                            formula survivorship_bias_flag                                expected_use
        broad_stock_bull_confirmed NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
               narrow_bull_warning NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
             neutral_stock_risk_on NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
        neutral_stock_chop_warning NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
          recovery_stock_confirmed NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
             fake_recovery_warning NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
broad_vs_narrow_bull_quality_score NOT_CREATED_NO_STOCK_BREADTH_PANEL   NO_STOCK_PANEL_BUILT blocked until PIT stock breadth data exists
```

## Signal Validation Before Portfolio Build

No stock-breadth signal was validated because no stock-breadth panel exists. ETF/Phase 4B baseline validation was saved for comparison only.

```
                            signal                               data_source                               status  horizon_weeks asset_or_portfolio  active_weeks  active_forward_return  inactive_forward_return  hit_rate  adverse_event_frequency  same_state_lift  improves_over_etf_sector_breadth
        broad_stock_bull_confirmed                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
               narrow_bull_warning                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
             neutral_stock_risk_on                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
        neutral_stock_chop_warning                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
          recovery_stock_confirmed                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
             fake_recovery_warning                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
broad_vs_narrow_bull_quality_score                             stock_breadth NOT_VALIDATED_NO_STOCK_BREADTH_PANEL            NaN               none             0                    NaN                      NaN       NaN                      NaN              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0                SPY           149               0.015543                 0.007648  0.738255                 0.080537              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0                QQQ           149               0.015386                 0.011462  0.711409                 0.127517              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0               ggg1           149               0.007559                 0.005138  0.677852                 0.060403              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0       phase4b_best           149               0.009369                 0.005397  0.691275                 0.046980              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            8.0                SPY           149               0.026349                 0.016024  0.791946                 0.100671              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            8.0                QQQ           149               0.026403                 0.023854  0.711409                 0.147651              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            8.0               ggg1           149               0.012827                 0.010693  0.657718                 0.060403              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            8.0       phase4b_best           149               0.016577                 0.011169  0.718121                 0.060403              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY           13.0                SPY           149               0.041498                 0.026470  0.718121                 0.127517              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY           13.0                QQQ           149               0.047647                 0.038723  0.738255                 0.120805              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY           13.0               ggg1           149               0.021025                 0.017590  0.765101                 0.020134              NaN                             False
      etf_neutral_risk_on_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY           13.0       phase4b_best           149               0.026276                 0.018502  0.751678                 0.020134              NaN                             False
           etf_broad_bull_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0                SPY           430               0.011175                 0.007150  0.720930                 0.102326              NaN                             False
           etf_broad_bull_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0                QQQ           430               0.012790                 0.011484  0.693023                 0.151163              NaN                             False
           etf_broad_bull_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0               ggg1           430               0.005334                 0.005547  0.646512                 0.067442              NaN                             False
           etf_broad_bull_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            4.0       phase4b_best           430               0.006298                 0.005700  0.648837                 0.062791              NaN                             False
           etf_broad_bull_baseline ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH                    ETF_BASELINE_ONLY            8.0                SPY           430               0.020291                 0.015573  0.753488                 0.104651              NaN                             False
```

## Candidate Logic / Skip Reasons

```
                                     candidate                                                                                                logic                                 status                                                      reason
 improved_phase5_stock_breadth_neutral_risk_on                            Would reduce neutral_mixed BIL only when neutral_stock_risk_on is active. SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
   improved_phase5_broad_stock_bull_aggressive Would increase offense in calm/neutral/recovery_confirmed when broad_stock_bull_confirmed is active. SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
   improved_phase5_narrow_bull_caution_overlay              Would block over-aggressive SPY/QQQ/sector exposure when narrow_bull_warning is active. SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
 improved_phase5_recovery_stock_breadth_rerisk Would re-risk recovery_confirmed only with recovery_stock_confirmed and block fake_recovery_warning. SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
improved_phase5_stock_breadth_aggression_score              Would map a bounded stock breadth quality score into non-stressed offense/cash budgets. SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
```

## Full-Period Baseline Metrics

No Phase 5 candidate metrics exist because no candidate was built. Baseline metrics were saved for context.

```
      portfolio  ann_return  ann_vol   sharpe  max_drawdown    cvar_5  avg_BIL  avg_sector_sleeve_exposure  beta_spy  corr_spy
            QQQ    0.146918 0.198664 0.739527     -0.514472 -0.061888      NaN                         NaN  1.033657  0.914365
            SPY    0.105431 0.175737 0.599935     -0.546130 -0.058004      NaN                         NaN  1.000000  1.000000
    bench_60_40    0.080872 0.103078 0.784570     -0.313836 -0.032731      NaN                         NaN -0.046977 -0.080056
   phase4b_best    0.077603 0.080954 0.958606     -0.137725 -0.026683 0.235703                    0.100481 -0.032742 -0.071045
    phase4_best    0.076448 0.082190 0.930141     -0.143286 -0.026837 0.238877                    0.128902 -0.035138 -0.075099
    phase2_best    0.073892 0.078627 0.939780     -0.125043 -0.026048 0.246166                    0.000000 -0.032065 -0.071636
    phase3_best    0.072679 0.075242 0.965945     -0.119015 -0.024830 0.279285                    0.000000 -0.030418 -0.071013
           ggg1    0.071381 0.076248 0.936168     -0.117739 -0.025377 0.266580                    0.000000 -0.030808 -0.070976
       prod_pin    0.068923 0.077931 0.884416     -0.139754 -0.026181 0.283918                    0.000000 -0.024908 -0.056143
official_shadow    0.068584 0.077616 0.883625     -0.136741 -0.026085 0.285552                    0.000000 -0.024890 -0.056330
```

## State-By-State Baseline Context

```
      portfolio              state  ann_return   sharpe  max_drawdown
           ggg1         calm_trend    0.040851 0.513625     -0.139322
official_shadow         calm_trend    0.035659 0.385443     -0.162535
    phase2_best         calm_trend    0.041268 0.517105     -0.139793
    phase3_best         calm_trend    0.043578 0.587964     -0.122006
    phase4_best         calm_trend    0.046796 0.548294     -0.136643
   phase4b_best         calm_trend    0.043870 0.510065     -0.135916
       prod_pin         calm_trend    0.035584 0.384275     -0.164683
           ggg1      neutral_mixed    0.112112 1.461561     -0.091217
official_shadow      neutral_mixed    0.109536 1.454915     -0.091444
    phase2_best      neutral_mixed    0.117435 1.468792     -0.097213
    phase3_best      neutral_mixed    0.112714 1.461507     -0.093329
    phase4_best      neutral_mixed    0.115123 1.393738     -0.106797
   phase4b_best      neutral_mixed    0.120736 1.474212     -0.106241
       prod_pin      neutral_mixed    0.110433 1.462193     -0.089670
           ggg1 recovery_confirmed    0.025705 0.344267     -0.053798
official_shadow recovery_confirmed    0.025594 0.374730     -0.050069
    phase2_best recovery_confirmed    0.026741 0.346583     -0.053930
    phase3_best recovery_confirmed    0.024606 0.322523     -0.054834
    phase4_best recovery_confirmed    0.039650 0.489707     -0.056432
   phase4b_best recovery_confirmed    0.043660 0.562973     -0.052874
       prod_pin recovery_confirmed    0.026147 0.384677     -0.049659
           ggg1   recovery_fragile    0.066671 1.142121     -0.032194
official_shadow   recovery_fragile    0.067696 1.284597     -0.031330
    phase2_best   recovery_fragile    0.069606 1.156644     -0.032387
    phase3_best   recovery_fragile    0.067719 1.174409     -0.031296
    phase4_best   recovery_fragile    0.080334 1.317319     -0.030419
   phase4b_best   recovery_fragile    0.077134 1.277422     -0.030084
       prod_pin   recovery_fragile    0.069735 1.316840     -0.030885
           ggg1     stressed_panic    0.035803 0.480687     -0.121622
official_shadow     stressed_panic    0.034331 0.513980     -0.117446
```

## Risk / Realism / Bias Checks

```
                                     portfolio    status  return_improvement_from_beta  disguised_spy_qqq  cash_reduction_too_large  stock_breadth_source_survivorship_biased  relies_on_diagnostic_only_data  max_drawdown_exceeds_mandate  stressed_panic_worsens  signal_active_windows_improve  signal_improves_beyond_etf_sector_breadth                                                      reason
 improved_phase5_stock_breadth_neutral_risk_on NOT_BUILT                           NaN              False                     False                                     False                           False                         False                   False                          False                                      False NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
   improved_phase5_broad_stock_bull_aggressive NOT_BUILT                           NaN              False                     False                                     False                           False                         False                   False                          False                                      False NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
   improved_phase5_narrow_bull_caution_overlay NOT_BUILT                           NaN              False                     False                                     False                           False                         False                   False                          False                                      False NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
 improved_phase5_recovery_stock_breadth_rerisk NOT_BUILT                           NaN              False                     False                                     False                           False                         False                   False                          False                                      False NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
improved_phase5_stock_breadth_aggression_score NOT_BUILT                           NaN              False                     False                                     False                           False                         False                   False                          False                                      False NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP
```

## Selection Table

```
                                     portfolio               classification                                                      reason stock_breadth_source  point_in_time_safe  survivorship_bias_acceptable  candidate_artifacts_built
 improved_phase5_stock_breadth_neutral_risk_on DATA_ONLY_NO_PORTFOLIO_BUILD NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP                 none               False                         False                      False
   improved_phase5_broad_stock_bull_aggressive DATA_ONLY_NO_PORTFOLIO_BUILD NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP                 none               False                         False                      False
   improved_phase5_narrow_bull_caution_overlay DATA_ONLY_NO_PORTFOLIO_BUILD NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP                 none               False                         False                      False
 improved_phase5_recovery_stock_breadth_rerisk DATA_ONLY_NO_PORTFOLIO_BUILD NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP                 none               False                         False                      False
improved_phase5_stock_breadth_aggression_score DATA_ONLY_NO_PORTFOLIO_BUILD NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP                 none               False                         False                      False
```

## Audit Results

Audits skipped because no portfolio candidate was built.

```
audit candidate                         status
 none      none SKIPPED_NO_PORTFOLIO_QUALIFIER
```

## Final Recommendation

**Recommendation:** `PROCEED_TO_DATA_UPGRADE_FOR_POINT_IN_TIME_STOCK_BREADTH`

**Best candidate:** `none`

**Rationale:** No local individual-stock price panel or point-in-time universe membership exists, so true stock breadth cannot be built without unacceptable survivorship-bias risk.

## Next Phase Prompt Outline

```
Phase 5A Point-in-Time Stock Breadth Data Upgrade prompt outline:
1. Do not change production, official shadow, or GGG1 pins.
2. Add a documented PIT stock universe source: effective-date index constituents, adjusted prices, delisting handling, and sector classifications.
3. Build lagged weekly stock breadth features only from members known as of each week.
4. Validate breadth signals against ETF breadth baselines before any portfolio build.
5. Trade ETFs only; no individual-stock sleeve.
6. Reject promotion if survivorship bias, lookahead, or 2022/stressed protection cannot be controlled.
```

## Resume / Project Story Summary

Phase 5 tested whether true stock breadth could be added as a signal input while continuing to trade ETFs. The answer from the local repo is data-first: the ETF universe is clean and broad enough for the existing system, but there are no individual-stock prices, no constituent lists, and no point-in-time membership. Because current-constituent breadth would be survivorship-biased and non-promotable, Phase 5 stopped before portfolio construction. The correct next move is a point-in-time stock breadth data upgrade, not another ETF-sector threshold pass and not individual-stock trading.
