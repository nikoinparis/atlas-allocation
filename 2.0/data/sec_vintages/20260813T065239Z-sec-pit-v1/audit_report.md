# Live SEC vintage audit

Structural audit: **True**. The vintage contains **57,736** canonical fact events for **20** companies and **1,270** accessions, including **453** amendment events.

Accession join coverage is **99.92%**; filings carrying precise acceptance timestamps are **100.00%**. Unexpected-unit rows: **1**. The filing-aware quarterly builder produced **1,076** company-decision rows across **58** decisions.

Pilot-viable factor inputs (>=70% recent coverage across >=14 companies): **31**: `assets, equity, equity_to_assets, debt_to_assets, cash, cash_to_assets, net_income, operating_cash_flow, revenue, net_margin, shares_outstanding, operating_cash_flow_margin, diluted_shares, net_income__yoy_growth, diluted_shares__yoy_growth, revenue__yoy_growth, operating_cash_flow__yoy_growth, share_repurchases, repurchases_to_revenue, debt_current, share_repurchases__yoy_growth, debt_noncurrent, operating_income, liabilities, liabilities_to_assets, operating_margin, capital_expenditure, capital_expenditure_to_revenue, free_cash_flow_margin, capital_expenditure__yoy_growth, operating_income__yoy_growth`. Pilot factor diagnostics authorized: **True**. Strategy promotion remains prohibited because the universe is not survivorship-safe and a delisting-complete stock-price panel is absent.
