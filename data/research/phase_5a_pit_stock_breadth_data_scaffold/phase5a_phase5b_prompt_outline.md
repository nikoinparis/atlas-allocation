# Phase 5B Prompt Outline - PIT Stock Breadth Signal Validation And ETF Allocation

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
