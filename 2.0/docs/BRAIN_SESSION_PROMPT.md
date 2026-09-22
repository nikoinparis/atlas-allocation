# Handoff prompt for a local session with BRAIN access

The cloud session that scoped this work cannot reach `api.worldquantbrain.com` — the host is
denied by its egress policy. Everything touching the platform has to run on the owner's
machine. Paste the block below into a Claude Code session opened in the local clone.

Kept in the repo so it can be re-issued without reconstructing it.

---

```
You are picking up an experiment on the atlas-allocation project. Work on the branch
claude/modest-mccarthy-vbgoak — `git fetch origin && git checkout claude/modest-mccarthy-vbgoak && git pull`.

READ FIRST, before doing anything:
  - CLAUDE.md at the repo root — it governs how this project works and is not optional
  - 2.0/docs/WORLDQUANT_BRAIN_EVALUATION_V1.md — the full plan and the run log at the bottom
  - 2.0/scripts/run_worldquant_brain_decile_ladder_v1.py — the runner you will be using

WHAT THIS IS, IN ONE PARAGRAPH
This project has 315 recorded research steps, nineteen closed signal families, and zero
promoted strategies. Its central finding is that none of its signals has cross-sectional
skill: nought of thirteen dashboard signals and nought of fourteen closed families order
their deciles, monotonicity within ±0.17 of zero for every one. We are NOT searching for a
new strategy on WorldQuant BRAIN. We are replicating that null on data the project does not
own, because BRAIN removes four stated weaknesses of the finding at once: a panel we built,
a universe we restricted, a construction-error history, and our own backtester. Both
outcomes are valuable and the flat one is expected.

NON-NEGOTIABLE GUARDRAILS — these override any convention you find on the platform or in
BRAIN community material:
  1. BRAIN's scoreboard is NOT the evidence. Sharpe, fitness and turnover are what this
     project was reading before Step 296, and reading them produced eleven years of headline
     numbers that all died. The evidence is DECILE MONOTONICITY, which BRAIN does not
     report and which you construct from the decile ladder. Declared bar: above 0.5.
  2. NEVER flip a sign post hoc. BRAIN community guidance explicitly says a Sharpe of −1.8
     is "a good alpha with a minus sign missing." That advice is rejected here: post-hoc sign
     flipping doubles the search space for free and turns every refutation into a discovery.
     Step 286 recorded Form 4 as "refuted on sign, rather than flipped" and Step 282 refused
     to rescue a −28% book by reversing it. Hold that line.
  3. Density guard before any decile reading. A field below 50% coverage cannot be read on
     deciles at all — most of the cross-section becomes ties and the monotonicity number is
     uninterpretable rather than low. Step 298 nearly reported a discovery on a signal that
     was 93.3% zeros.
  4. Ignore any t-statistic the daily series implies. Quarterly fundamentals on a daily grid
     give roughly 16 independent decisions, not thousands. Step 303 recorded exactly this
     inflation. Monotonicity reads shape, not significance, which is why it carries the weight.
  5. Nothing is promoted out of this run whatever it shows. A signal that scores well is a
     reason to construct something and pre-register it, not a candidate.
  6. Report faithfully. If a step fails, say so with the output. Never record planned work
     as done.

STATE OF PLAY — established on 2026-09-22, do not re-derive
  - Settings in use: USA / TOP3000 / delay 1 / decay 0 / truncation 0.08 / pasteurization ON
    / nanHandling ON. Delay 1 is not negotiable; delay 0 is where same-bar lookahead lives.
  - The TRAIN window is 2019–2022 — FOUR YEARS, about 16 quarterly decisions, not the decade
    an earlier draft assumed. The gain from BRAIN is cross-sectional depth (~3,000 names
    against the 509 these signals have always used), not more decisions. 2019–2022 also sits
    inside Step 300's 2013–2022 window, so this replicates on independent DATA, not on an
    independent PERIOD.
  - Confirmed field ids that parse: assets, assets_curr, capex, cash, cash_st, cashflow,
    cashflow_op, cogs, current_ratio, debt, debt_lt, debt_st, ebit, ebitda, sales, equity,
    liabilities. Instrument coverage reads 50% with 100% date coverage.
  - `net_income` DOES NOT EXIST. The simulator rejects it: "Attempted to use unknown
    variable net_income". This blocks two of the three signals.
  - balance_sheet_quality ran and is WRONG-SIGNED: Sharpe −1.47, returns −10.38%, negative
    in all four years (−1.84, −1.30, −2.03, −1.22). Declared sign is positive. Three readings
    remain open — real inverted content (would be a 2020–21 junk-and-leverage regime bet, not
    an edge), a debt/liabilities definition difference against our SEC tag sums, or
    extremes-only concentration. The decile ladder separates them. The neutralization setting
    used for that run was never recorded — re-run it on SUBINDUSTRY so the number is readable.

YOUR TASKS, IN ORDER

1. Credentials. Check whether ~/.worldquant_brain.json exists. If not, run
   `2.0/scripts/setup_worldquant_brain.ps1` (Windows) which prompts for them without echoing.
   NEVER print, log, commit or echo the password. It is gitignored; keep it that way.

2. Phase 0. Run:
       python 2.0/scripts/run_worldquant_brain_decile_ladder_v1.py --phase0
   This downloads every relevant dataset's field dictionary to 2.0/data/worldquant_brain_fields/
   and prints candidates for the nine field ids the signals need. Commit the CSVs — the field
   dictionary on disk is what stops this blocking every future session.
   If BRAIN demands persona/biometric verification, say so and stop; it must be completed in
   a browser once.

3. Resolve net_income. From the Phase 0 output, identify the correct field id for net income
   and set it in the FIELDS dict at the top of the runner. Record the coverage figure. If no
   net income field exists at usable coverage, say so plainly — do NOT substitute ebit,
   ebitda or another proxy silently, because that changes what the signal is. If you must
   substitute, declare it as a construction difference in the doc's run log first.

4. Re-run the three production forms at neutralization SUBINDUSTRY and record Sharpe,
   returns, turnover and the per-year rows for each. Do not interpret them yet.

5. Establish the true window. Read the TEST / IS / OS tabs or the API and record the actual
   date ranges. Correct the run log if the total span is longer than TRAIN's 2019–2022.

6. Run the decile ladder — this is the actual experiment:
       python 2.0/scripts/run_worldquant_brain_decile_ladder_v1.py
   Ten long-only decile alphas per signal at neutralization NONE, plus a spread and a
   production form, plus the control_size negative control. These WILL fail BRAIN's
   submission checks; that is expected and irrelevant, we are not submitting anything.
   The script polls, reads each decile's `returns`, and computes monotonicity.
   If the API path breaks, fall back to `--print-expressions` in the web UI and
   `--score-manual` on the numbers read off the screen.

7. Record the result honestly:
   - append the numbers to the run log in 2.0/docs/WORLDQUANT_BRAIN_EVALUATION_V1.md
   - append a dated Step 316 to 2.0/PROJECT_HISTORY.md in the existing append-only style,
     including whatever failed
   - move queue item S13 in 2.0/docs/RESEARCH_QUEUE.md to the Closed table with a one-line
     verdict and the step number, per CLAUDE.md §3b
   - commit and push to claude/modest-mccarthy-vbgoak. Do not open a pull request.

HOW TO READ THE ANSWER — this is declared in advance, before you see any number
  - Monotonicity below 0.5 → the null replicates on independent data with a five-times
    deeper cross-section and someone else's backtester. This closes the "maybe our panel was
    wrong" objection permanently. It is the expected outcome and a genuinely valuable one.
    Write it up as such, not as a disappointment.
  - Monotonicity above 0.5 → the first real lead in 315 steps. The next question is NOT
    "trade it" — it is which panel is wrong, ours or theirs. Check field definitions,
    universe composition and restatement handling before believing anything.
  - A large top-minus-bottom spread with a flat ladder → concentration, not skill. Step 296
    found that shape six times: positive IC alongside a negative decile spread, which is what
    noise looks like measured twice.
  - The control_size ladder should be flat. If it orders itself, the harness is measuring
    something other than the signal and nothing else in the run is readable.

Tell me what you find, including anything that did not work.
```
