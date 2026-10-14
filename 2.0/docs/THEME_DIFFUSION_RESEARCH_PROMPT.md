# Research brief: theme diffusion ("AI is booming → what does AI need?")

Paste everything below the line into a new Claude Code session opened in this repository.

---

I want to research one strategy idea in the Portfolio Optimizer project (`2.0/`). Read `CLAUDE.md`,
`2.0/docs/RESEARCH_QUEUE.md` (item **A18** and the Closed table first), and Steps 343-352 of
`2.0/PROJECT_HISTORY.md` before proposing anything. Follow the project's rules: pre-register every
test in `2.0/config/` before computing a return, count every configuration tried, keep the
design and holdout windows separate, report negative results in the history and queue, and say
plainly what each result means.

## The idea

Every year some group of stocks rises for a reason that exists in the world before it shows in
prices. AI took off, AI needs GPUs, GPUs live in data centres, and data centres need power, cooling
and networking. I want to detect a rising theme early from text, map it to the companies exposed
to it, especially the **second-order beneficiaries** the market has not yet repriced, and hold a
diversified, risk-controlled basket of them.

## What is already known here (do not redo)

- Price momentum and "steady risers" held a year: high return, but a regime bet with −50%
  drawdowns and below-SPY risk-adjusted returns. Every safety net and boom-switching rule made it
  worse (Steps 347, 349, 352).
- Theme rotation by industry *price* momentum: 0 of 15 configurations beat SPY in 2012-2019
  (Step 349).
- News-level signals show nothing on their own: Wikipedia attention, earnings-call tone, GDELT
  coverage and tone (Steps 348, 350, 351). **So the hypothesis is diffusion to linked firms, not
  the news itself.**
- Supply-chain customer links failed on coverage (Steps 202-204).

## What I want you to do, in order

1. **Replicate a published version first.** Lee, Sun, Wang & Zhang (2019, JFE), "Technological
   links and predictable returns": firms linked by patent technology overlap, where linked firms'
   past returns predict the focal firm's return. Use the free USPTO PatentsView bulk tables
   (queue B13). The hard part is mapping patent assignees to SEC CIKs, so measure the match rate
   before anything else. Run the project's skill screen (rank IC, decile spread, monotonicity) on a
   window the signal was not chosen on.
2. **Firm-level theme exposure from text.** Use the Hassan, Hollander, van Lent & Tahoun (2019)
   method: the share of each company's earnings call devoted to a theme. Source: the free
   `kurry/sp500_earnings_transcripts` dataset used in Step 350. Expand each theme's seed words
   with embeddings trained **only on text before each decision date**.
3. **Detect themes automatically, never by hand.** Choosing "AI" because we know AI boomed is
   hindsight. Themes must come from a point-in-time process, such as topics whose share of news
   or call text is rising fastest (GDELT's THEMES field, or a topic model refit on past text only).
4. **Second-order reasoning with an LLM only if it cannot see the future.** A modern LLM knows
   NVIDIA won, so a backtest of its "what does AI need?" answers is contaminated. Either use a
   chronologically consistent model (He, Lv, Manela & Wu 2025, ChronoBERT/ChronoGPT) or test the
   LLM layer forward only, from today, untouched.
5. **Portfolio.** Exposure-weighted basket, spread across several themes, single-name and
   industry caps, no leverage, no shorts. Judge it against SPY at the same market risk, with
   costs of 0/10/50/100 bps, leave-one-name-out, and regimes 2012-2019, 2020, 2021-22 and
   2023-26.

## What I want back

A plain-language summary of what each step found, full metrics for anything that reaches a
backtest (CAGR, Sharpe, max drawdown, alpha vs same-risk SPY), and an honest verdict. If the
first step fails, say so and stop before building the later ones.
