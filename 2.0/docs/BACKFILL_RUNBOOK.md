# Price backfill runbook

The backfill acquires daily prices from 2011 for the survivorship-safe 2012-2026 issuer
universe. It is the single piece of work that unblocks most of the research programme,
because every signal this project has tested was tested on a 143-week bull sample.

## What it is doing and why it takes so long

17,970 request pairs across 12,846 issuers. Tiingo's free tier allows 50 requests an hour
and 1,000 a day, so a complete run is about 36 unattended days.

The obvious shortcut is to acquire only the 3,253 issuers already in the price panel, which
takes about 9 days. **Do not do this and then research the result.** The current panel is
the *current* SEC universe; 8,830 issuers filed during 2012-2026 and stopped before it
begins. A panel of survivors only would be more biased than the short sample it replaced,
not less. Tier 1 exists so that something is usable early, not so that it can be researched
alone.

## Running it

Set the token for the process only. Never put it in a file, a config, a commit, or a log.

    export TIINGO_API_TOKEN=your_token
    ./scripts/run_daily_backfill_shift_v1.sh

One shift spends the day's budget and stops. It is safe to run twice, safe to interrupt, and
resumes where it stopped; every issuer gets a terminal record written before the next is
attempted, so a kill costs at most one issuer.

To run it continuously instead of a shift at a time:

    export TIINGO_API_TOKEN=your_token
    python3 scripts/run_price_backfill_daemon_v1.py

To see what it would do without contacting anyone:

    python3 scripts/run_price_backfill_daemon_v1.py --dry-run

## Scheduling it

**On your own machine** — add to `crontab -e`, adjusting the path and putting the token in a
file only your user can read (`chmod 600`):

    17 0 * * * cd /path/to/2.0 && TIINGO_API_TOKEN=$(cat ~/.tiingo_token) ./scripts/run_daily_backfill_shift_v1.sh

Runs at 00:17 daily, shortly after the quota resets.

**In a Claude Code environment** — a daily Routine is already registered
(`Daily Tiingo price backfill shift`, 00:17 UTC). It checks reachability first and exits
quietly if the environment cannot reach Tiingo, so it costs nothing while blocked. For it to
do real work the environment needs two things:

1. `TIINGO_API_TOKEN` set as an environment variable in the environment's configuration.
2. A network policy that permits `api.tiingo.com`. The default policy in the environment this
   was built in returns 403 on CONNECT to Tiingo, Twelve Data and Stooq alike. Network policy
   is chosen when an environment is created — see
   https://code.claude.com/docs/en/claude-code-on-the-web.

## Watching progress

Each shift appends to `data/price_backfill_2012_v1/progress.jsonl` and writes a log under
`data/price_backfill_2012_v1/logs/`. The shift script prints a summary at the end.

Expected statuses:

- `acquired` — history saved.
- `rejected_name_mismatch_or_ticker_reuse` — the provider's issuer name did not match the
  SEC name as filed. This is the **expected** failure mode, not a bug: tickers get recycled,
  and accepting a recycled ticker's history would silently attach one company's prices to
  another company's fundamentals. The second request is not spent on these.
- `empty_history` — the symbol exists but has no prices in the requested window.
- `http_error_404` — no such symbol at the provider. Terminal.
- `http_error_429` / `request_error_*` — transient. Not terminal, retried on a later shift.

## Before researching the result

Two gates, both mandatory:

1. **Tier 2 must be complete.** Tier 1 alone is the survivorship bias this exists to remove.
2. **Delisting returns must be handled.** 8,830 issuers stop trading inside the sample. If
   their final return is missing or silently set to the last traded price, the panel is
   *optimistically* biased — a worse failure, in a more dangerous direction, than the bias it
   was built to fix. The terminal-outcome machinery from Steps 153-160 needs extending to
   cover them.

## If the token leaks

Rotate it at tiingo.com. The free tier is rate-limited rather than billed, so the exposure is
quota theft rather than cost, but rotate anyway.
