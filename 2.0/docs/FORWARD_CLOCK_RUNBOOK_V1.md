# Friday runbook: starting and running the residual sleeve's forward clock

Decision taken 2026-09-05: **start the clock as declared.** The protocol is not
modified. `config/forward/sec_residual_controlled_sleeve_forward_v1.json` keeps every
constant it was frozen with on 2026-08-24, including the 0.8/0.2 sleeve split, 50bps,
and the residual signal's declared parameters.

The 2026-08-28 and 2026-09-04 windows lapsed with no packet and cannot be backfilled,
so the first decision is **2026-09-11**, and the clock completes no earlier than
2027-09-10. Missing a Friday does not pause the clock; it costs a week permanently.

## Before you start

Every command below is research-only. No script in this sequence is authorised to
place an order, and all of them refuse to run with `live_trading_enabled` set.

Windows are wall-clock and unforgiving. The recorder accepts a packet only when its
`observed_at_utc` falls inside `[Friday 21:00 UTC, the following Friday 21:00 UTC)`.
Build the packet *after* 21:00 UTC on the decision Friday; a packet built early is
refused, correctly, and the fix is to rebuild it, not to edit it.

## First decision — Friday 2026-09-11, after 21:00 UTC

    # 1. Fresh prices. The sleeve paths end 2026-08-07 and the overlay needs the
    #    decision Friday itself, so neither of these is optional. The ETF file is
    #    a separate source and ends 2026-08-07 too; forgetting it fails late.
    ./.venv/bin/python scripts/acquire_yahoo_recent_current_sec_prices_v1.py
    ./.venv/bin/python scripts/acquire_free_etf_snapshot.py

    # 2. Extend both sleeve return paths through 2026-09-11. The control's
    #    11-week overlay reads these two files and nothing else; feeding it
    #    candidate_path_50bps.csv instead is the circular input of Step 213.
    ./.venv/bin/python scripts/run_sec_growth_survivorship_retest_v1.py
    ./.venv/bin/python scripts/build_cash_conversion_sleeve_path_v1.py

    # 3. Re-run the reconstruction sweep. Gates set by the owner: selection must
    #    match on 100% of comparable dates, overlay on at least 99%. Below either
    #    bar, stop and do not submit a packet.
    ./.venv/bin/python scripts/build_control_composite_book_v1.py \
        --decision-date 2026-09-11 --verify sec_cash_conversion_breadth20_dynamic_v1

    # 4. Assemble the packet.
    ./.venv/bin/python scripts/build_residual_sleeve_decision_packet_v1.py \
        --decision-date 2026-09-11

    # 5. Record it, and both companions alongside.
    ./.venv/bin/python scripts/record_sec_residual_controlled_sleeve_forward_v1.py \
        --decision-packet evidence/forward_sec_residual_controlled_sleeve_v1/incoming/decision__2026-09-11.json
    ./.venv/bin/python scripts/record_equal_weight_benchmark_forward_v1.py \
        --decision-date 2026-09-11
    ./.venv/bin/python scripts/record_residual_tie_agnostic_companion_forward_v1.py \
        --decision-date 2026-09-11

Step 3's `--verify` returns a non-zero exit status when the reconstruction does not
reproduce the reference. Note the trap found on 2026-09-05: it *also* returns non-zero
when the audit reference does not cover the selection quarter at all, reporting
`selection_expected: 0`. That is a missing reference, not a mismatch. Read the
`verification` block before acting on the exit code.

## Every Friday after that, from 2026-09-18

    ./.venv/bin/python scripts/acquire_yahoo_recent_current_sec_prices_v1.py
    ./.venv/bin/python scripts/acquire_free_etf_snapshot.py

    # decision packet for this Friday, then the observation packet for the week
    # that just completed, then the three recorders
    ./.venv/bin/python scripts/build_residual_sleeve_decision_packet_v1.py \
        --decision-date <that Friday>
    ./.venv/bin/python scripts/build_residual_sleeve_observation_packet_v1.py \
        --realization-date <that Friday>
    ./.venv/bin/python scripts/record_sec_residual_controlled_sleeve_forward_v1.py \
        --decision-packet evidence/forward_sec_residual_controlled_sleeve_v1/incoming/decision__<that Friday>.json
    ./.venv/bin/python scripts/record_sec_residual_controlled_sleeve_forward_v1.py \
        --observation-packet evidence/forward_sec_residual_controlled_sleeve_v1/incoming/observation__<that Friday>.json
    ./.venv/bin/python scripts/record_equal_weight_benchmark_forward_v1.py \
        --decision-date <that Friday> --realize
    ./.venv/bin/python scripts/record_residual_tie_agnostic_companion_forward_v1.py \
        --decision-date <that Friday> --realize

A realization needs security-level total returns for every held name. An unpriced
holding is an error, not a zero: the recorder refuses the packet rather than quietly
treating a missing price as a flat week.

Each decision packet carries a `price_identity` map so the realization side never has
to guess where a name is priced: 46 of the 48 rehearsed holdings resolve to a `cik10` in
`data/clean_weekly_prices_v2/` and `data/broad_full_history_panel_v1/`, and XLE and XLK
resolve to the ETF weekly price file. The books are keyed by ticker, the price panels by
CIK, and that map is not injective, so inverting it a week after the fact would be a
guess. It travels inside the hashed packet instead.

`build_residual_sleeve_observation_packet_v1.py` reads the recorded decision, verifies
the packet on disk against the `decision_packet_sha256` in the log, prices every held
name through the `price_identity` map, and refuses outright if any holding is unpriced.
Rehearsed on the week ending 2026-08-07 it priced all 48 holdings, 46 from the narrow
panel and 2 from the ETF file, best PLTR +39.78%, worst TTD -23.50%.

Asked for the week ending 2026-08-14 it refuses, because the ETF file stops at
2026-08-07. That is the acquisition step above failing loudly a week early rather than
a fabricated flat week entering the log, and it is worth seeing once.

## Rehearsing without touching the clock

    ./.venv/bin/python scripts/build_residual_sleeve_decision_packet_v1.py \
        --decision-date <a past Friday> --rehearsal

Rehearsal packets are written to `evidence/forward_sec_residual_controlled_sleeve_v1/rehearsal/`
and are labelled `"rehearsal": true`. They are refused by the recorder on their dates,
which is the point. The full-chain rehearsal on 2026-09-05 found a real defect this way
-- the assembler emitted no `snapshot_id`, and the recorder raised `KeyError` on it --
six days before that failure would have happened against a deadline.

## What the clock will and will not tell you

It will tell you whether this specific composite, as frozen, earns its keep over 52
untouched weeks against an equal-weight portfolio of the same universe recorded beside
it.

It will not tell you whether residual momentum works. The residual leg's book is drawn
from a tie pool of roughly 59 identically-scored names by a `cik10`-ascending sort, so
the forward record measures one arbitrary draw. See Step 234 in `PROJECT_HISTORY.md`
and the note appended to `FORWARD_CLOCK_DECISION_V1.md`.

The tie-agnostic companion answers that separately, and its reading is pre-declared in
`config/forward/residual_tie_agnostic_companion_v1.json` before any of its results
exist. It records 22 books every week on identical prices -- the declared one, the whole
tie pool, and twenty pre-declared random tie-breaks -- so the only difference between
the series is which names each holds. If the declared book lands inside the central 90%
of the seeds over 52 weeks, its in-sample 99th-percentile position was luck.
