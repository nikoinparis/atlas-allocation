# Research brief: theme diffusion ("AI is booming → what does AI need?")

Paste everything below the line into a new Claude Code session opened in this repository.

---

I want to develop one strategy idea in the Portfolio Optimizer project (`2.0/`). **This session is
for refining the idea, not for running backtests yet.** Read `CLAUDE.md`, then
`2.0/docs/RESEARCH_QUEUE.md` (item **A18**, and the Closed table first), then Steps 343-352 of
`2.0/PROJECT_HISTORY.md`, so you know what has already been tried.

## The idea, in my words

Every year some group of stocks rises for a reason that exists in the world before it shows up in
prices. AI took off, AI needs GPUs, GPUs sit in data centres, and data centres need power,
cooling and networking. I want to spot a rising theme early from what is happening in the world
(news, earnings calls, filings, patents or anything else useful), work out which companies
benefit, especially the *second-order* ones the market has not caught up with yet, and hold a
diversified basket of them without taking on too much risk or drawdown.

## What has already been learned here

- Buying stocks that are already rising (momentum, "steady risers") earned high returns, but it
  was a bet on booming markets: −50% drawdowns, below-SPY risk-adjusted returns. Every safety net
  and every "switch out when the boom ends" rule made it worse (Steps 347, 349, 352).
- Rotating into industries whose prices are rising did not beat SPY (Step 349).
- News about a company on its own predicted nothing: Wikipedia attention, earnings-call tone,
  GDELT news coverage and tone (Steps 348, 350, 351). If this idea works, it is more likely
  through *slow spread to linked companies* than through the news itself.
- A published result points that way: Lee, Sun, Wang & Zhang (2019, JFE), "Technological links and
  predictable returns". Companies linked by patents tend to follow their linked peers' returns.
- Any AI or LLM reasoning ("what does AI need?") cannot be honestly backtested with a modern model,
  because it already knows how things turned out. Chronologically consistent models exist
  (He, Lv, Manela & Wu 2025, ChronoBERT/ChronoGPT); otherwise that part can only be tested going
  forward.

## What I want from this session

1. **Double-check the idea.** Is the reasoning sound? Where is it most likely to fail? Is there
   research that supports or contradicts it? Look things up, and say which sources you actually read
   and which you are recalling.
2. **Suggest how it could work better.** You are not tied to my framing or to the outline above. If
   you find a different or better angle, or something unrelated that could clearly benefit the
   project, raise it and explain why. Add any new idea to the research queue as you go.
3. **Design the pieces and give me options with trade-offs for each:**
   - **Spotting a theme:** what data, how to tell a real rising theme from noise, and how to make
     sure themes are found automatically from information available at the time, not hand-picked
     with hindsight.
   - **Mapping a theme to companies:** first-order and second-order beneficiaries, and which
     methods (earnings-call text, 10-K text, patents, supply chains, industry codes, embeddings,
     LLMs) are free, testable without look-ahead, and realistic here.
   - **Building the portfolio:** how many names, how to weight them (by exposure, equal, risk-based),
     how to spread across themes and industries, when to enter and exit a theme, how often to
     rebalance, and how to keep drawdowns and turnover reasonable without the safety nets that
     already failed here.
   - **Testing it honestly:** which windows, what to compare against, which costs, how many variants
     we can afford to try, and what result would count as a pass or a fail, written down before
     anything runs.
4. **Data and effort:** what is free, what is already on disk, what the hardest blocker is (for
   example matching patent holders or news names to company IDs), and roughly how many sessions
   each piece would take.
5. **End with a refined design and a recommended first step.** Include the questions you need me to
   answer. Don't build or backtest anything until I have agreed to the design.

Keep the explanations in plain language. Put the conclusion first, then the detail, and end with a
short list of what you need from me.
