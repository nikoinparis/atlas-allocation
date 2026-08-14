# Split-normalized SEC valuation pilot v1

Market capitalization uses raw close and the latest SEC shares-outstanding fact known before each decision. Shares are carried forward only by stock splits occurring after the fact period and on or before the price date. Adjusted close appears only in the distortion audit and never in a valuation signal.

Best factor: `sales_yield`; holdout CAGR 41.25%, Sharpe 1.637, drawdown -19.43%. Best benchmark: `benchmark::XLK` at 31.70%.

This remains a non-promotable current-survivor pilot. Its purpose is to establish a mechanically valid valuation pipeline before a broader survivorship-aware retest.
