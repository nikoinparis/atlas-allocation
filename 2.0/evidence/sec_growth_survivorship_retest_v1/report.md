# SEC growth survivorship-aware retest v1

The unchanged growth rule was tested across **14** point-in-time quarterly decisions. At 50-bps costs, the base scenario produced **31.70% CAGR**, **0.948 Sharpe**, and **-36.50% maximum drawdown**. The mandatory adverse missing-company scenario produced **16.69% CAGR**, **0.597 Sharpe**, and **-45.60% drawdown**. SPY returned **22.32% CAGR** on the same weekly span.

From the old pilot's holdout start, the survivorship-aware base CAGR was **37.24%** versus the old 20-survivor pilot's **36.14%**. The old pilot is not used as a valid benchmark claim. No strategy is automatically promoted; the paired result and validation checks determine the next decision.

## Recent-return and cost audit

At the primary 50-bps cost assumption, trailing one-year CAGR was **142.22%**,
Sharpe was **2.332**, and maximum drawdown was **-23.44%**. The result remained
high at 100-bps and 200-bps costs, with trailing one-year CAGRs of **140.23%**
and **136.29%**, respectively. Full-period base CAGR fell from **31.70%** at
50 bps to **26.80%** at 200 bps. The adverse full-period CAGR fell from
**16.69%** to **12.17%**.

The recent result is materially concentrated. During the latest holding period
beginning April 3, 2026, Micron returned **159.39%** and supplied **67.63%** of
the five-stock portfolio's positive arithmetic return. If Micron's 20% weight
had instead remained in cash, the other four weights would have contributed
only **15.25%**, versus **47.13%** with all five holdings. This is a diagnostic,
not a revised strategy or a tuned exclusion rule.

## Verdict

This is a valid survivorship-aware research candidate, but it does not replace
the ETF incumbent. The base case beat SPY over the full recent span, but it
trailed XLK's **36.59%** CAGR and had worse drawdown and Sharpe. The mandatory
adverse case trailed SPY. The base/adverse gap comes from Meta Materials (MMAT),
which was selected twice in early 2023 but has no validated local price history.
Both paths are identical from the old pilot's August 2023 holdout start onward.
Keep the strategy as a separate fundamental sleeve candidate and require more
out-of-sample history before promotion.
