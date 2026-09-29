# A12 — five new hypotheses on WorldQuant BRAIN, pre-registered

*Written 2026-09-29, committed before the first A12 simulation. Machine-readable twin:
`config/worldquant_brain_a12_v1.json` — if the two ever disagree, the JSON is the registration.*

## What this is for, in plain words

Every earlier BRAIN run (Steps 315-320) replicated this project's null on signals the project
already had. A12 asks a different question: **do information channels this project has never
had access to — analyst estimates, analyst recommendations, option prices — show real
cross-sectional skill?** "Skill" means the one thing Step 296 made the deciding measurement:
the ten deciles of the signal line up in order, better than a no-skill control that scores
the same names. BRAIN Sharpe is reported and ignored (Step 317: Sharpe 1.44, monotonicity
+0.042).

A BRAIN pass would be a **map of which data is worth paying for**, not a strategy: BRAIN
data cannot be exported, and its book (daily, dollar-neutral, ~3,000 names long and short)
is not something a small account can run.

## Channels, and why none is in the Closed table

| # | channel | nearest closed item | why it is different |
|---|---|---|---|
| H1 | analyst estimate **revision breadth** | SUE/PEAD (reported surprise), Step 317 fundamentals | forward-looking analyst *changes*, not reported numbers; queue A5, never tested |
| H2 | analyst **forecast dispersion** | none | disagreement between analysts; needs per-estimate data we never had |
| H3 | options **implied-volatility smirk** | `pcr_oi_30` put/call open interest (Step 320) | that was *positioning* (quantities); this is *pricing* of downside tails |
| H4 | options **call-minus-put IV spread** | short interest (Step 263), FINRA short volume (Step 282) | that was the *quantity* shorted; this is the *price* of shorting as implied by options |
| H5 | sell-side **recommendation changes** | none (P2 `ConsRecomm` is queued, blocked on paid data) | analyst opinion changes; the P2 purchase question in miniature |

News sentiment (Ravenpack), social sentiment, peer spillover, low volatility, and every
fundamental ratio family are closed and are not touched.

## Settings (all runs)

USA / TOP3000 / delay 1 / decay 0 / truncation 0.08 / pasteurization ON / nanHandling ON.
Delay 0 is forbidden. Decile ladders at neutralization MARKET (as the Step 317/320 search,
where the full-coverage cap control read +0.091 / middle-8 −0.119). Production forms at
SUBINDUSTRY, reported only. 50 requests/minute respected.

## The hypotheses

Every expression carries its declared sign inside it. Decile 10 is always the declared
"good" end. A ladder that reads INVERTED refutes the hypothesis; **the sign is never flipped.**

### H1 — Analyst revision breadth (sign: positive)
**Why it should work.** Analysts revise slowly and in herds; a stock with more upward than
downward estimate revisions tends to keep drifting up as the market under-reacts to the
information (Chan, Jegadeesh & Lakonishok 1996; the "earnings momentum" literature).
**Fields** (`analyst4`, VECTOR, coverage 0.734): `anl4_basicconafv110_pu` ("number of upper
estimations"), `anl4_basicconafv110_down` ("number of lower estimations"),
`anl4_basicconafv110_numest`. **Interpretation risk, declared now:** read as consensus up/down
revision counts; BRAIN does not document the counting window, and if "upper" means "above
consensus" this is an estimate-skew measure with no prior. Up/down counts were chosen over a
change in the consensus mean because a per-share mean jumps mechanically on a stock split.

- H1a `group_rank((vec_avg(pu) - vec_avg(down)) / vec_avg(numest), sector)`
- H1b same inside `ts_mean(·, 21)`
- H1c same inside `ts_mean(·, 63)`

(full ids in the JSON). Density probe on all three — a count difference is exactly zero
whenever up = down.

### H2 — Analyst forecast dispersion (sign: negative)
**Why it should work.** When analysts disagree and short-selling is costly, prices reflect the
optimists, so high-dispersion stocks are overpriced and subsequently underperform (Diether,
Malloy & Scherbina 2002; Miller 1977). **Known confound, declared now:** dispersion is high
for small, volatile, near-zero-earnings firms, so the coverage-matched size control matters
more here than anywhere.
**Fields** (`analyst4`, MATRIX): `anl4_fs_detail_estimates_basic_af_v4_nd_eps_std` (cov 0.673),
`..._eps_mean` (0.992), `anl4_afv4_eps_high` / `anl4_afv4_eps_low` (1.0), `close`.

- H2a `group_rank(-(eps_std / abs(eps_mean)), sector)` — the paper's scaling
- H2b `group_rank(-(eps_std / close), sector)` — price scaling, no near-zero denominator
- H2c `group_rank(-((eps_high - eps_low) / close), sector)` — range, denser field

### H3 — Implied-volatility smirk (sign: negative)
**Why it should work.** Informed traders with bad news buy out-of-the-money puts, which
steepens the smirk before the news reaches the stock; steep-smirk stocks underperform (Xing,
Zhang & Zhao 2010). **Field** (`option8`, cov 0.951): `implied_volatility_mean_skew_{30,90}`,
described as mean IV at 90% strikes minus mean IV at 110% strikes, so higher = steeper.

- H3a `group_rank(-implied_volatility_mean_skew_30, sector)`
- H3b `group_rank(-implied_volatility_mean_skew_90, sector)`
- H3c `group_rank(-ts_mean(implied_volatility_mean_skew_30, 20), sector)` — slower, cheaper to trade

### H4 — Call-minus-put implied-volatility spread (sign: positive)
**Why it should work.** Under put-call parity ATM call and put IVs should match. When call IV
sits above put IV, informed buying of calls (or cheap borrowing) is showing; when put IV sits
above, the stock is expensive to short or informed traders are buying puts. High spread
predicts higher returns (Cremers & Weinbaum 2010; Bali & Hovakimian 2009). Later work
attributes much of this to stock-lending fees, which makes it the *price* of shorting — the
dimension Step 263's short *interest* (a quantity) did not measure. **Fields** (`option8`,
cov 0.973): `implied_volatility_call_{30,90}`, `implied_volatility_put_{30,90}`.

- H4a `group_rank(implied_volatility_call_30 - implied_volatility_put_30, sector)`
- H4b the same at 90 days
- H4c the 30-day spread minus its own 20-day mean — the change form

### H5 — Recommendation changes (sign: positive)
**Why it should work.** Changes in consensus recommendations predict returns better than the
level (Jegadeesh, Kim, Krische & Lee 2004): an upgrade carries new information, a stale
"buy" does not. **Fields** (`analyst4`, VECTOR, cov 0.624 — just above the floor):
`anl4_buy`, `anl4_under`, `anl4_total_rec`. Net buy share =
`(vec_avg(anl4_buy) - vec_avg(anl4_under)) / vec_avg(anl4_total_rec)`.

- H5a `group_rank(ts_delta(net_buy_share, 21), sector)`
- H5b the same over 63 days
- H5c the same over 126 days

Density probe on all three — recommendations change rarely, so a 21-day change may be zero
for most names. **Expected to be at risk on density; if it fails, that is the result.**

## Controls — coverage-matched, one per hypothesis mask

`group_rank(cap + 0 * <hypothesis mask>, sector)` — market cap ranked within sector on
exactly the names the hypothesis scores (C1 → H1, C2 → H2, C3 → H3 and H4, C4 → H5). Step 317
showed a control on a different coverage measures a different universe (+0.867 vs +0.091).
Scored-name counts are compared after the run to confirm the masks match.

## Density guard (first) and tie check (every ladder)

- Probe `if_else(abs(<variant>) > 0, 1, 0)` at MARKET: longCount = non-zero names. A variant
  with fewer than 50% of the 3,000-name universe non-zero is **UNREADABLE**, no ladder runs,
  and nothing replaces it.
- Every decile of every ladder must hold 5-15% of that alpha's scored names, else the ladder
  is UNREADABLE (ties) and not scored.

## The bar — declared now

A variant is a **lead** only if **all** hold:
1. `verdict()` = ORDERS ITS DECILES (full > 0.5 and middle-8 > 0.5, same direction, positive
   in the declared sign);
2. full > its control's full **and** middle-8 > its control's middle-8;
3. passes the tie check;
4. joint permutation p (random orderings of its own ten decile returns, 200,000 draws) below
   Bonferroni **0.05 / 317** (every earlier simulation on the account counted as a trial —
   the conservative count; the construction count, 19 + 15 = 34, is reported beside it);
5. full-ladder monotonicity > 0 in at least 4 of 5 calendar years (BRAIN's yearly-stats
   recordset, no extra simulations);
6. a de-sized ladder (`group_rank(<inner>, bucket(rank(cap), buckets=5))`) still reads > 0.5.

Anything short of that is recorded as what it is (flat, concentration, inverted, below
control). A lead is **not** a strategy: nothing is promoted and nothing is submitted.

## Budget

15 alphas (5 × 3) · 6 density probes · 15 production forms · 150 ladder simulations ·
4 control ladders (40) · at most 3 de-sized ladders (30, conditional). **Maximum 241
simulations.** Not exceeded, and no hypothesis is substituted.

## Can we use it? — the question recorded per hypothesis

For each result the write-up states: the BRAIN fields; whether an equivalent is obtainable
outside BRAIN (free: SEC/FINRA/CFTC/free APIs, or collected forward ourselves; paid: vendor
and rough cost); and whether the traded form could be run by an individual (shorting, turnover
× costs at 10 and 50 bps, number of names). Declared expectation before the run: **none of
the five channels has a free point-in-time history**; all five could be collected forward from
free snapshots, which gives no history for years.

## Addendum 1 — 2026-09-29, written mid-run, BEFORE any control ladder existed

**Declared honestly as written after data was seen.** The density probes had run (H1a 26.1%
and all three H5 variants 0.3% non-zero: UNREADABLE, not substituted), and the H1b and H1c
ladders had come back visibly ordered (decile 1 about −8%, decile 10 about +7%). No control
ladder and no score had been computed; one H2 decile had landed. (A first commit of this
addendum, d367260, carried only the runner change because the doc edits failed to save; it is
recorded here rather than rewritten. Between that failed save and this one, H1c decile 10's
yearly returns were read — 2019 −0.2%, 2020 +6.4%, 2021 +23.7%, 2022 +8.9%, 2023 −5.4% — so
test 3 below is no longer blind for that one decile; it is a read-out, not a gate, and is
unchanged by it.)

These additions can only **kill** H1, never promote it. They are the adversarial pass CLAUDE.md
§1 requires and were not in the original plan, which is a deviation and is reported as one.

1. **Momentum control** — the obvious alternative explanation. Analysts revise after prices
   move, so revision breadth may be price momentum relabelled (momentum is closed here, Steps
   189/192/257). Ladder on
   `group_rank(ts_sum(returns, 63) + 0 * <H1 raw breadth>, sector)` — 63-day past return on H1's
   exact mask. 10 simulations.
2. **Momentum-neutral revision breadth** — the decisive test. H1c's inner signal ranked within
   past-return quintiles: `group_rank(<H1c inner>, bucket(rank(ts_sum(returns, 63)), buckets=5))`.
   If revision breadth has content beyond momentum this still orders its deciles (> 0.5 full
   and middle-8); if it goes flat, H1 was momentum. 10 simulations.
3. **Backfill check** — `analyst4`'s revision fields were created on BRAIN on 2022-07-01, so
   2019 to mid-2022 is vendor history loaded after the fact and may not be point-in-time.
   From the yearly-stats already fetched (no new simulations): report 2023 — the only year
   collected entirely after the field went live — separately. A signal that orders strongly
   in 2019-2021 and not in 2023 is flagged as possibly backfill-contaminated.

New maximum: 157 run or scheduled + 20 here + ≤30 conditional de-sized = **207**, inside the
registered 241. Bar for H1 to remain a lead: all six original bars **and** test 2 reads
ORDERS ITS DECILES. Test 1 is reported, not a gate (a control can order itself).

## Honest limits, stated before the run

- In-sample on the platform (the window is expected to be 2019-2023; read off the first alpha).
  Post-publication for all five papers, but searched by thousands of BRAIN users.
- ~20 quarterly-scale decisions; significance is weak evidence (Step 296's limit). Shape carries
  the weight.
- Three of five hypotheses share `analyst4` and two share `option8`; they are five hypotheses,
  not five independent datasets.

## Addendum 2 — 2026-09-30, after 197 simulations were scored, BEFORE any corrected run

**A defect voided two gates.** `bucket(rank(x), buckets=5)` — the de-sizing form copied from
Step 317 — is a **single group**. BRAIN's `buckets` argument is a *string of boundaries*
(`buckets="2,5,6,7,10"`, or `range="0, 1, 0.1"`), so one boundary at 5 on a 0-1 rank puts every
name in one bucket and `group_rank` becomes a plain universe-wide rank. Found because H1c
"de-sized by size quintiles" and H1c "momentum-neutral by return quintiles" came back with
**identical decile returns to four decimals**. Voided: Addendum 1 test 2 (momentum-neutral
H1c), bar 6 (de-sizing) for H1c and H4b, and Step 317's `news_impact_DESIZED` read and its
de-size validation.

Known at the time of writing: H1c and H4b met bars 1-5; H1c's momentum-neutral v1 and both
v1 de-sized ladders are no-op readings. Corrected, kill-only re-runs with `range="0,1,0.2"`
(quintile groups):

- momentum-neutral H1c v2 — H1c's inner signal ranked within 63-day-return quintiles
- de-sized H1c v2 — within market-cap quintiles
- de-sized H4b v2 — within market-cap quintiles

Each v2 ladder must differ from its v1 no-op ladder, or the grouping is still inert and the test
is void. Gates: H1c stays a lead only if both H1c v2 ladders read ORDERS ITS DECILES; H4b only
if its v2 ladder does. +30 simulations: 227 in total, above Addendum 1's 207, **inside the
original 241**.
