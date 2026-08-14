# Batch 1 Source-Health Screening

Audit time: 2026-08-08T18:44:20.746921+00:00

This is a repository-health and installation-triage screen. It is not a code audit, strategy validation, security certification, endorsement, or evidence of profitability.

## Outcome

- isolated_smoke_test_candidate: 18
- manual_review_before_sandbox: 15
- reference_only_for_now: 8

Health bands:
- caution: 6
- high_risk_or_insufficient_evidence: 5
- promising_screening_signals: 9
- strong_screening_signals: 21

License review states:
- custom_license_manual_legal_review: 1
- manually_confirmed_copyleft_review_obligations: 1
- manually_confirmed_permissive: 1
- no_top_level_license_detected: 5
- recognized_copyleft_review_obligations: 6
- recognized_permissive: 23
- source_available_noncommercial_restriction: 1
- source_available_restricted_commercial_use: 3

## Isolated smoke-test candidates

| Project | Score | Activity | License | Install | Primary role signals |
|---|---:|---|---|---|---|
| [Tradingview Screener API](https://github.com/jmargieh/tradingview-screener) | 95 | active_0_180_days | MIT | low | crypto;screening |
| [barter-rs](https://github.com/barter-rs/barter-rs) | 90 | active_0_180_days | MIT | medium | backtesting;live_execution;event_driven |
| [vnpy](https://github.com/vnpy/vnpy) | 85 | active_0_180_days | MIT | medium | live_execution;crypto |
| [QuantConnect](https://github.com/QuantConnect/Lean) | 85 | active_0_180_days | Apache-2.0 | medium_high | live_execution |
| [zvt](https://github.com/zvtvz/zvt) | 85 | active_0_180_days | MIT | low | backtesting |
| [Hikyuu](https://github.com/fasiondog/hikyuu) | 85 | active_0_180_days | Apache-2.0 | medium_high | unspecified |
| [bt](https://github.com/pmorissette/bt) | 85 | active_0_180_days | MIT | low | backtesting |
| [Investing Algorithm Framework](https://github.com/coding-kitties/investing-algorithm-framework) | 85 | active_0_180_days | Apache-2.0 | low | backtesting;live_execution |
| [qf-lib](https://github.com/quarkfin/qf-lib) | 85 | active_0_180_days | Apache-2.0 | low | backtesting;event_driven;crypto |
| [the0](https://github.com/alexanderwanyoike/the0) | 85 | active_0_180_days | Apache-2.0 | medium_high | live_execution |
| [PythonTradingFramework](https://github.com/JustinGuese/python_tradingbot_framework) | 85 | active_0_180_days | MIT | low | backtesting;live_execution;portfolio_management |
| [flashalpha-fill-simulator](https://github.com/FlashAlpha-lab/flashalpha-fill-simulator) | 85 | active_0_180_days | MIT | low | options |
| [finmarketpy](https://github.com/cuemacro/finmarketpy) | 80 | active_0_180_days | Apache-2.0 | low | backtesting |
| [Cipher](https://github.com/nanvel/cipher-bt) | 80 | maintained_181_365_days | MIT | low | backtesting;crypto |
| [QUANTAXIS](https://github.com/yutiansut/QUANTAXIS) | 75 | active_0_180_days | MIT | medium_high | live_execution |
| [aat](https://github.com/AsyncAlgoTrading/aat) | 75 | active_0_180_days | Apache-2.0 | medium_high | live_execution;event_driven;crypto;options |
| [hftbacktest](https://github.com/nkaz001/hftbacktest) | 70 | maintained_181_365_days | MIT | medium | backtesting;crypto;high_frequency |
| [QuantFabric](https://github.com/QuantFabric/QuantFabric) | 70 | active_0_180_days | MIT | low | unspecified |

## Manual review or reference-only queue

| Project | Score | Action | Concerns |
|---|---:|---|---|
| [PandoraTrader](https://github.com/pegasusTrader/PandoraTrader) | 35 | manual_review_before_sandbox | license_not_detected |
| [FlashFunk](https://github.com/HFQR/FlashFunk) | 45 | manual_review_before_sandbox | license_not_detected |
| [backtrader](https://github.com/mementum/backtrader) | 50 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [Gunbot Quant](https://github.com/GuntharDeNiro/gunbot-quant) | 50 | manual_review_before_sandbox | no_GitHub_Actions_workflows_detected;no_top_level_test_indicator_detected;no_GitHub_release_detected;screening_score_is_triage_not_code_quality_or_profitability |
| [WonderTrader](https://github.com/wondertrader/wondertrader) | 55 | manual_review_before_sandbox | no_GitHub_Actions_workflows_detected;no_top_level_test_indicator_detected;no_GitHub_release_detected;screening_score_is_triage_not_code_quality_or_profitability |
| [FinHack](https://github.com/FinHackCN/finhack) | 60 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [PyBroker](https://github.com/edtechre/pybroker) | 75 | manual_review_before_sandbox | source_available_license_restricts_commercial_use |
| [Rqalpha](https://github.com/ricequant/rqalpha) | 75 | manual_review_before_sandbox | source_available_license_restricts_commercial_use |
| [backtesting.py](https://github.com/kernc/backtesting.py) | 80 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [QTradeX](https://github.com/squidKid-deluxe/QTradeX-Algo-Trading-SDK) | 80 | manual_review_before_sandbox | custom_license_requires_legal_review |
| [Manifold-BT](https://github.com/manifoldbt/manifoldbt) | 85 | manual_review_before_sandbox | source_available_license_restricts_commercial_use |
| [pysystemtrade](https://github.com/pst-group/pysystemtrade) | 85 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [vectorbt](https://github.com/polakowo/vectorbt) | 85 | manual_review_before_sandbox | source_available_license_restricts_commercial_use |
| [nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 90 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [lumibot](https://github.com/Lumiwealth/lumibot) | 100 | manual_review_before_sandbox | copyleft_obligations_require_review |
| [Better Quant](https://github.com/byrnexu/betterquant) | 15 | reference_only_for_now | stale_over_two_years;license_not_detected |
| [fund-strategy](https://github.com/SunshowerC/fund-strategy) | 15 | reference_only_for_now | stale_over_two_years;license_not_detected |
| [sdoosa-algo-trade-python](https://github.com/sreenivasdoosa/sdoosa-algo-trade-python) | 15 | reference_only_for_now | stale_over_two_years;license_not_detected |
| [gobacktest](https://github.com/gobacktest/gobacktest) | 20 | reference_only_for_now | repository_archived |
| [Botvana](https://github.com/featherenvy/botvana) | 50 | reference_only_for_now | stale_over_two_years;copyleft_obligations_require_review |
| [fastquant](https://github.com/enzoampil/fastquant) | 50 | reference_only_for_now | stale_over_two_years |
| [quanttrader](https://github.com/letianzj/quanttrader) | 60 | reference_only_for_now | stale_over_two_years |
| [zipline](https://github.com/quantopian/zipline) | 60 | reference_only_for_now | stale_over_two_years |

## Interpretation rules

- Missing machine-readable license metadata blocks installation until the actual license is reviewed.
- Copyleft projects remain candidates, but integration boundaries and distribution obligations require review.
- Archived or stale projects remain available as design references and strategy ideas.
- GitHub Actions and top-level test folders are only screening signals; deeper code review may find more or less coverage.
- Popularity contributes no points. Stars and forks are recorded as context only.
