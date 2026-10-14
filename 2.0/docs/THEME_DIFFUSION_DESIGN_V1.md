# Theme diffusion — design v1 (A18)

*2026-10-14. Design only: nothing in this document has been built or backtested. Step 353.*

## Conclusion first

1. **The economics are sound, but only one part of the idea can be tested on history, and the
   published evidence on that part has weakened since 2005.** "Spot the theme" has too few
   independent examples to test: perhaps 10–30 real themes in twenty years, and AI, data centres
   and power are one bet, not three. "Buy the firms linked to what is already moving" is testable
   on thousands of firms every month. It is the part the published research supports, and the part
   that has decayed most.
2. **The risk is buying a theme after its prices have already moved.** Specialised (thematic) ETFs
   launch when a theme is popular, and over their first five years they lose about 30% on a
   risk-adjusted basis, because the stocks they hold were overvalued at launch (Ben-David,
   Franzoni, Kim & Moussawi, RFS 2023). A book that buys what news and earnings calls are excited
   about is, by default, that ETF. The edge, if there is one, is in linked firms whose prices have
   **not** moved yet.
3. **The linked-firm effects have faded since they were published, on data already on disk.**
   The Open Source Asset Pricing returns in `data/osap_vintages/` carry five of these
   "linked-firm" signals. Every one was strong in 1990–2004, and none has had a t-statistic above
   1.5 since 2013 (table below). This project's own reading of a product-overlap peer signal on
   BRAIN (Step 320) ordered only its extreme deciles, not the middle eight. Ali & Hirshleifer
   (Step 205) find that these spillovers are all one effect, best captured by shared analyst
   coverage. That needs IBES data, which is not free here.
4. **Recommended first step: one cheap test that could kill the idea.** Use the Hoberg–Phillips
   product-similarity network (free, 1989–2023, never used here). Score each firm by its
   text-linked peers' recent returns, and run the standard skill screen with a shuffled-network
   placebo. **My prior that it passes is low, roughly one in ten; that is a judgement, not a
   number.** It is still worth one or two sessions. The whole idea rests on this mechanism: if it
   fails, theme detection has no slow spread to exploit, and A18 becomes a forward-only record. If
   it passes, it is the first signal in 353 steps to do so, and theme detection then has something
   to feed.
5. **Theme detection and the LLM step come second.** Theme detection is built only if step 4
   passes. The LLM "what does AI need?" step is forward-only regardless.

## 1. Is the reasoning sound? Where does it break?

| link in the chain | sound? | where it most likely fails |
|---|---|---|
| Themes have real-world causes that precede prices | Yes, sometimes | Usually prices move first or at the same time. Steps 348–351 found news about a company predicts nothing, and Step 306 found 97% of the price response arrives the same day |
| You can spot a theme early from text | Partly | By the time a phrase appears in many earnings calls, the obvious stocks have moved. The theme-ETF evidence says this is where most money is lost |
| First-order beneficiaries are clear | Yes, and so they are priced | NVDA was obvious to everyone. Greenwood, Shleifer & You (JFE 2019): industries that ran up 100% have a far higher crash probability, though not lower average returns. This is the Step 347 −50% drawdown pattern |
| Second-order beneficiaries are mispriced for a while | **The only plausible edge** | Strong before ~2005, weak since (table below). Step 320: extremes only, no ordering |
| A diversified basket controls the risk | Partly | Themes are correlated (one macro bet), and a theme basket will carry high beta and a growth/volatility tilt. Step 352: switching rules make it worse; only the sleeve size controls risk |
| History is a fair test | **Theme level: no.** Firm level: yes | We know which themes won. Ten to thirty themes cannot produce a significance test. Any LLM after 2023 knows the outcome |

**Survivorship of themes is the core hindsight trap.** AI → GPUs → power is memorable because it
worked. The same reasoning in real time also produced 3D printing (2013), blockchain (2017–18),
cannabis (2018), hydrogen, EVs, SPACs and clean energy (2020–21), and the metaverse (2021–22).
Every one had real-world causes, rising mentions in earnings calls and obvious "picks and shovels".
Any historical test must find themes with a fixed algorithm and score all of them, duds included.

### Published linked-firm returns, from the OSAP file on disk

Long-short portfolio returns, annualised mean of monthly returns, t-statistic on monthly. A
literature check, not a test of any strategy here. Source:
`data/osap_vintages/20260905T082446Z-osap-oct2025/long_short_returns_wide.csv`.

| signal (paper) | 1990–2004 | 2005–2012 | 2013–2019 | 2020–2024 |
|---|---|---|---|---|
| CustomerMomentum (Cohen & Frazzini 2008) | +14.8%, t 2.4 | +4.6%, t 1.1 | +0.6%, t 0.2 | +5.9%, t 0.8 |
| iomom_cust (Menzly & Ozbas 2010) | +7.7%, t 2.0 | +4.1%, t 1.4 | +1.9%, t 0.5 | −1.9%, t −0.3 |
| iomom_supp (Menzly & Ozbas 2010) | +10.0%, t 3.2 | +2.1%, t 0.8 | +0.8%, t 0.2 | −0.9%, t −0.1 |
| retConglomerate (Cohen & Lou 2012) | +15.1%, t 3.8 | +10.2%, t 2.3 | +5.3%, t 1.3 | +1.3%, t 0.2 |
| IndRetBig (Hou 2007, big-to-small lead-lag) | +32.2%, t 5.8 | +12.7%, t 2.9 | +5.6%, t 1.4 | +2.7%, t 0.5 |
| Mom12m (own momentum, for reference) | +7.1%, t 0.8 | +3.9%, t 0.4 | +12.3%, t 1.7 | +19.7%, t 1.4 |

Lee et al.'s technology-link signal is not in OSAP. I found no out-of-sample replication of it
after 2012. The pattern above suggests it decayed as well.

## 2. A better framing

**Make it a firm-level signal, not a choice of themes.** The question "which theme is next?" has
no testable history. The question "which firms are linked to something that just moved, and
have not moved themselves?" can be asked of every firm every month. The theme then becomes
whatever is moving in a firm's linked neighbourhood, so nobody has to choose it. In 2023, NVDA's
surge would have raised the score of every firm whose 10-K describes adjacent products, and
lowered it again once those firms caught up.

Three angles that follow from this, all added to the queue:

- **A19 — text-peer gap (the recommended first step).** Hoberg–Phillips TNIC peers, scored on
  their past returns. Hoberg & Phillips (JFQA 2018) report that most of the effect comes from
  peers that do *not* share the firm's SIC code. That is "second-order, not yet noticed" in
  measurable form.
- **A20 — peers' fundamental news, not their prices.** Lee et al. find the same lead-lag in
  earnings surprises and analyst revisions. A firm whose linked peers just reported strong revenue
  growth or earnings surprises gets the information through demand, not through price, and the
  data is already on disk (SUE panel, Company Facts). Caution, recalled rather than read:
  Thomas & Zhang (JAR 2008) report that late announcers *overreact* to early announcers' news, so
  the sign is not guaranteed.
- **B15 — thematic ETF launches as a "theme already priced" marker.** When a theme ETF launches,
  or its inflows surge, Ben-David et al. say the theme is priced. That gives an exit rule that is
  not a price-based safety net, the kind of rule Steps 349 and 352 showed cannot be timed. SEC
  N-PORT holdings are free from 2019.

**Something unrelated that would help the project:** the `gvkey_ciks` table in Ian Gow's `farr`
package (MIT, 48,517 links, with dates) maps Compustat gvkey to SEC CIK. That one table makes
several free academic datasets usable here for the first time: TNIC, DISCERN patents and others
keyed on gvkey. It is worth acquiring regardless of A18.

## 3. Design options

### 3a. Spotting a theme (phase 2, built only if A19 or A20 passes)

| option | data | free / on disk | point-in-time | strength | weakness |
|---|---|---|---|---|---|
| **A. Emerging phrases in earnings calls** (Hassan et al. 2019, Sautner et al. 2023 method) | HF `kurry/sp500_earnings_transcripts`, 2005–2025 | free; tones on disk, raw text deleted (3.5 GB to re-fetch) | yes, dated calls | Managers talk about orders and capex before analysts do | S&P 500 only (the Step 254 size bias); large caps discuss themes once already priced |
| **B. Emerging phrases in 10-K Item 1** | EDGAR | free; script exists, corpus deleted, 2019+ only | yes, by filing date | covers every filer, including small caps | annual and clustered in Q1 (the Step 255 power problem) |
| **C. Fast-growing patent classes** | PatentsView / USPTO bulk, CPC codes | free; B13 | grant date is public | real R&D, not talk | lags by 2–3 years; misses business-model themes |
| **D. GDELT themes field** | GDELT GKG | free; only organisation counts kept | yes | broad world news | Step 351 found news-level signals empty |
| **E. LLM proposes themes** | any | API cost | **no**, unless forward-only or a dated model | best reasoning | look-ahead (Sarkar & Vafa; Glasserman & Lin) |

**Recommended: A for discovery, with B for small-cap exposure, and no human seed words.** The
rule, fixed in advance: each quarter, using text up to that date only, a two-word phrase is a
candidate theme if (i) it was in under 0.5% of filers three years earlier, (ii) its share of firms
has grown for two consecutive quarters, and (iii) it appears in at least three SIC2 industries.
Condition (iii) is what separates a real theme from one company's jargon. Phrases that occur
together in the same calls are grouped into themes. **Real versus noise cannot be settled at the
theme level.** The honest check is descriptive: publish the full list the algorithm found for
2008–2025, duds included. Then judge only the firm-level return signal.

### 3b. Mapping a theme to firms

| method | first / second order | free | look-ahead risk | realistic here |
|---|---|---|---|---|
| **TNIC product similarity (Hoberg–Phillips)** | second (peers outside SIC) | yes, 1989–2023 | low, but the file is **not lagged**; it must be dated by the 10-K filing | **yes, 1–2 sessions**; gvkey→CIK via `farr` |
| Own-text exposure (share of call or 10-K about the theme) | first | yes | low | yes, once 3a exists |
| Patent technology links (Lee et al.) | second | yes: DISCERN 2.0 to 2021 (gvkey), Stoffman match to 2023 (permco) | medium: matching uses later ownership history | 2–3 sessions; patenters only, ~1,000 firms, so the density guard applies |
| Customer–supplier links from 10-K text | second | yes | low | Step 203 extractor reached 80% precision against an 85% gate; OSAP shows customer momentum dead since 2013 |
| SIC / industry codes | first | yes | none | closed (Step 349, sector rotation) |
| Embeddings (sentence models) | either | yes | medium: models were trained on later text | prefer TF-IDF fitted on past text only |
| LLM ("what does AI need?") | second, best reasoning | API cost | **high** for any history | **forward-only**; DatedGPT (annual cutoffs 2013–2024) and ChronoGPT exist but are small models |

**Hardest blocker: identity mapping.** TNIC and DISCERN are keyed on gvkey, and `farr` resolves
that. PatentsView raw assignees and news names need fuzzy name matching, the problem that sank
Steps 288, 345 and 351. Avoid those sources until a gvkey route is exhausted. For forward use past
2023 we must rebuild product similarity from our own 10-K corpus (2–3 sessions), because the TNIC
library updates only every couple of years.

### 3c. Building the portfolio (only after a signal passes the screen)

| choice | options | recommendation and why |
|---|---|---|
| direction | long-only / beta-hedged / long-short | **owner decides** (Step 346 removed financing). Long-only means the result is mostly beta, so it must be reported against a beta-matched benchmark |
| names | 20 / 50 / 100 | **50–100**: the signal is weak, the edge is breadth, and Step 279 showed 20-name books act like 5–7 bets |
| weights | by exposure / equal / inverse volatility | **inverse volatility with a 2% cap**. Exposure weighting buys pure plays, the Step 347 volatility bet |
| spread | theme caps / industry caps | **20% per SIC2 and per TNIC cluster**, and report effective bets. Caps did not help Step 279, but these books have the opposite problem |
| entry and exit | price-based timing / signal decay | **signal decay only**: hold while the gap is open, sell when the firm catches up. No market or trend switch; Steps 349 and 352 measured those making things worse |
| rebalance | monthly / quarterly | **monthly with a buffer**: enter in the top 10%, exit below the top 30%. Lee et al. find the effect over 1–6 months |
| drawdown control | timing overlays / sleeve size | **sleeve size** within a core (for example 70% core, 30% sleeve). That is what Step 352 found actually works |

### 3d. Testing honestly (pre-registered before any data is touched)

- **Windows:** design 2012–2018, holdout 2019–2023 (TNIC ends 2023), regimes reported 2012–19,
  2020, 2021–22 and 2023. 2008–09 cannot be tested: the daily panel starts in 2011. 2024 onward is
  forward, or uses our own rebuilt similarity.
- **Screen (as Steps 296–343):** rank IC at 1 month (and 3 months), top-minus-bottom decile spread,
  `ds.clears()` on the full ladder **and** the middle eight, the density guard, the same sign in
  both halves, worst leave-one-SIC2-out, and leave-top-10-names-out.
- **Placebo, required:** 200 shuffled networks that keep each firm's number of peers. This separates
  "linked by text" from "has many peers".
- **Controls, declared:** the signal is residualised each month on the firm's own 1-month and 12-1
  momentum and its SIC2 industry return. Cohen & Frazzini's own warning (Step 203) is that link
  momentum can be industry momentum in disguise.
- **Comparisons (only if a book is built):** SPY, beta-matched SPY/T-bills, the equal-weight
  universe, the Step 347 steady-riser book (correlation, to show this is a different bet), and FF6
  alpha. Costs at 0, 10, 50 and 100 bps.
- **Trial budget: four.** T1 all TNIC peers at 1 month; T2 non-SIC peers only at 1 month; T3 the
  peer-minus-own gap over 6 months; T4 = T2 at 3 months. Bonferroni at 0.05 / 4 = 0.0125, stacked on
  the project's cumulative search and reported as such.
- **Pass:** at least one trial clears Bonferroni **and** `ds.clears()` **and** the placebo 95th
  percentile in the design window, with the same sign and `ds.clears()` again in the 2019–2023
  holdout. **Fail:** anything else. The pv13 pattern (strong extremes, flat middle) is a fail,
  declared now.

## 4. Data and effort

| piece | data | status | sessions |
|---|---|---|---|
| A19 TNIC peer-gap screen | TNIC-3 zip, `farr` gvkey_ciks, daily prices 2011–2026 on disk | to fetch (small), never used here | **1–2** |
| A20 peers' fundamental news | SUE panel, Company Facts (S10 needs re-acquisition), TNIC from A19 | mostly on disk | 1–2 after A19 |
| Patent tech links | DISCERN 2.0 (404 MB), PatentsView CPC | to fetch | 2–3 |
| Theme discovery from calls and 10-Ks | HF transcripts (re-fetch), EDGAR 10-K (extend to 2011, S1) | scripts exist | 3–4 |
| Own product-similarity rebuild for 2024+ | 10-K corpus | depends on the above | 2–3 |
| LLM beneficiary map, forward shadow | API | needs a key and spend sign-off (C4) | 1 to set up, then a weekly clock |
| B15 theme ETF marker | N-PORT 2019+ | free, never used | 2 |

## 5. Refined design and the first step

**Phase 1 (now, if approved): A19 alone.** Fetch TNIC-3 and `farr`'s `gvkey_ciks`. Gate on mapping
coverage: at least 70% of liquid price-panel issuers per year must get a TNIC peer set, or the run
stops as inconclusive. Write `config/tnic_peer_gap_registry_v1.json` with the four trials and the
pass/fail rule above. Then run the screen, and build no book unless it passes.

**Phase 2 (only if phase 1 passes):** A20 on the same network, then theme discovery (3a, option A)
as a filter: does the peer gap work better when the moving peers are exposed to an emerging
theme? Then a book (3c) and the full gate list.

**Phase 3 (in parallel, whatever phase 1 finds, if the owner approves the spend):** a frozen-prompt
LLM that maps algorithm-found themes to second-order beneficiaries monthly, recorded forward only
and read on the decile ladder after at least 12 months. Merged into C4 rather than run as a
second LLM clock.

**If phase 1 fails:** close A18's diffusion arm, keep only phase 3, and record that the free form of
the second-order mechanism is gone in this sample.

## Sources

Read this session (abstracts, readmes or summaries; no full paper texts):
- Ben-David, Franzoni, Kim & Moussawi, "Competition for Attention in the ETF Space", RFS 36(3), 2023 — [SFI](https://sfi.ch/en/publications/competition-for-attention-in-the-etf-space), [NBER w28369](https://www.nber.org/system/files/working_papers/w28369/revisions/w28369.rev2.pdf)
- Hoberg & Phillips, "Text-Based Industry Momentum", JFQA 53(6), 2018 — [Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/textbased-industry-momentum/6E04891A7AD30C24C21CBDE37EC06BF4)
- Hoberg–Phillips Data Library, TNIC — [data page](https://hobergphillips.tuck.dartmouth.edu/tnic_basedata.html), [TNIC-3 readme](https://hobergphillips.tuck.dartmouth.edu/idata/Readme_tnic3.txt) (gvkey1/gvkey2/score; year = fiscal year; "not lagged")
- Lee, Sun, Wang & Zhang, JFE 132(3), 2019 — [RePEc](https://ideas.repec.org/a/eee/jfinec/v132y2019i3p76-96.html), [Alpha Architect](https://alphaarchitect.com/2019/09/technological-links-and-predictable-returns/)
- Greenwood, Shleifer & You, "Bubbles for Fama", JFE 131(1), 2019 — [NBER w23191](https://www.nber.org/system/files/working_papers/w23191/w23191.pdf)
- Glasserman & Lin, look-ahead bias in GPT sentiment — [arXiv 2309.17322](https://arxiv.org/abs/2309.17322); Sarkar & Vafa — [ICML 2025](https://icml.cc/virtual/2025/48685); DatedGPT — [arXiv 2603.11838](https://arxiv.org/pdf/2603.11838)
- Sautner, van Lent, Vilkov & Zhang, "Firm-level Climate Change Exposure", JF 2023 — [SSRN](https://papers.ssrn.com/abstract=3642508)
- `farr` gvkey_ciks — [r-packages.io](https://r-packages.io/datasets/gvkey_ciks); DISCERN 2.0 — [Zenodo](https://zenodo.org/records/13619821); Stoffman/Woeppel/Yavuz patent–CRSP match — [Dropbox page](https://paper.dropbox.com/published/Patent-CRSP-permco-match--A40KaHJizoJRoM96nAWe6wzqBg-jQI7RUCIX90KPp5jrHs66u0)
- Kelly, Papanikolaou, Seru & Taddy, AER: Insights 2021 — [NBER w25266](https://www.nber.org/papers/w25266)

Read in earlier steps of this project: Cohen & Frazzini 2008 (Step 203), Ali & Hirshleifer
(Step 205), Hassan et al. 2019 and He, Lv, Manela & Wu 2025 (verified in A18).

Recalled, not read: Thomas & Zhang 2008 (late-announcer overreaction); Pastor & Veronesi 2009
(technological revolutions and bubble-like prices); McLean & Pontiff 2016 (anomaly decay after
publication); Menzly & Ozbas 2010, Cohen & Lou 2012 and Hou 2007, beyond their OSAP series.
