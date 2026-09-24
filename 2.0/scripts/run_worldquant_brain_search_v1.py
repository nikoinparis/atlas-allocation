"""Search BRAIN for a submittable alpha -- scored against a no-skill control, not a bar.

This is a DIFFERENT ACTIVITY from run_worldquant_brain_decile_ladder_v1.py and is kept in a
separate file on purpose. That script ran a pre-registered diagnostic: replicate the Step
296-308 null on data this project does not own. It did, and it is finished -- ten of twelve
families measured, zero beat a no-skill size control.

This script searches. The owner directed it explicitly on 2026-09-24. The terms are frozen in
config/worldquant_brain_search_v1.json, written before any search result existed.

THE ONE THING THAT MAKES THIS DIFFERENT FROM SCOREBOARD FISHING:

  Every candidate is scored against control_size, which is `group_rank(assets, sector)` --
  ranking companies by total assets, no skill in it whatever. That control orders its deciles
  at monotonicity +0.867 / middle-8 +0.905 market-neutral on ten clean deciles.

  Four of the ten families measured clear the declared 0.5 bar. ALL FOUR clear it by roughly
  the margin the control does. The highest of them, sales_yield at +0.988, is sales over
  market cap -- a size ranking with extra steps. A bar of 0.5 rediscovers size. The control
  is the bar.

AND THE SECOND THING: every candidate is also run DE-SIZED, and the de-sizing method is itself
validated by requiring that a de-sized control_size goes flat. If a candidate's ordering
survives de-sizing it is not size. If it does not, it was.

Nothing here authorizes a submission. That is a separate, explicit owner decision.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ladder", Path(__file__).with_name("run_worldquant_brain_decile_ladder_v1.py"))
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)

# The control this whole script is scored against. Measured 2026-09-22, MARKET-neutral,
# 10/10 clean deciles, no timeouts.
CONTROL_MONOTONICITY = 0.867
CONTROL_MIDDLE_8 = 0.905

# Candidates. Sign declared with the expression, before the ladder runs -- never after.
#
# Sentiment first, for three recorded reasons: coverage 1.0 against the fundamentals' 0.5,
# which removes the density caveat on every diagnostic number; socialmedia8 has 6,299 users
# and news18 8,996 against fundamental6's 86,751, so less of the platform's uncountable
# search has landed there; and a z-scored sentiment LEVEL is structurally far less size-linked
# than a ratio whose denominator is market capitalisation.
CANDIDATES: dict[str, str] = {
    # --- raw sentiment levels, coverage 1.0 -----------------------------------------
    "social_sentiment":        "group_rank(scl12_sentiment, sector)",
    "twitter_z_sentiment":     "group_rank(snt_social_value, sector)",
    "ravenpack_equity_sent":   "group_rank(equity_sentiment_score, sector)",
    "ravenpack_earnings_sent": "group_rank(earnings_evaluation_sentiment, sector)",

    # --- sentiment dynamics, not level ----------------------------------------------
    # Declared sign: improving sentiment ranks high. A 20-day change, not a level, so it
    # cannot be a static quality/size proxy the way a level can.
    "sentiment_momentum_20d":  "group_rank(ts_delta(ts_mean(scl12_sentiment, 5), 20), sector)",
    "twitter_sent_momentum":   "group_rank(ts_delta(ts_mean(snt_social_value, 5), 20), sector)",
    # Declared sign: attention SPIKE ranks high -- buzz relative to its own trailing norm.
    "buzz_surprise":           "group_rank(scl12_buzz / (ts_mean(scl12_buzz, 60) + 0.001), sector)",
}

# Every candidate above is also run in this de-sized form. `{x}` is the candidate.
DESIZE = "({x}) - group_rank(cap, {g})"

# Validation of the de-sizing method itself. If this does NOT go flat, de-sizing is broken
# and no de-sized number in the run is readable.
DESIZE_CONTROL = "group_rank(assets, {g}) - group_rank(cap, {g})"


def ladder(session, expression: str, neutralization: str, group: str,
           quiet: bool = False) -> dict:
    """Ten long-only decile alphas, then the shape statistics."""
    returns: dict[int, float] = {}
    for decile in range(1, 11):
        band = (f"if_else(rank({expression}) > "
                f"{-1.0 if decile == 1 else (decile - 1) / 10.0}, 1, 0)"
                f" - if_else(rank({expression}) > {decile / 10.0}, 1, 0)")
        result = L.simulate(session, band, neutralization)
        if "error" in result:
            print(f"      decile {decile:2d}: {result['error'][:70]}", flush=True)
            returns[decile] = float("nan")
            continue
        returns[decile] = L.statistic(result["alpha"], "returns")
        if not quiet:
            print(f"      decile {decile:2d}: {returns[decile]:+.4f}", flush=True)
    return dict(L.ladder_shape(returns), decile_returns=returns)


def verdict_against_control(shape: dict, desized: dict | None) -> str:
    mono, middle = shape["monotonicity"], shape["monotonicity_middle_8"]
    if mono != mono:
        return "DEGENERATE -- not readable"
    if mono <= CONTROL_MONOTONICITY:
        return (f"BELOW CONTROL ({mono:+.3f} vs {CONTROL_MONOTONICITY:+.3f}) -- "
                "measuring size, not skill")
    if middle != middle or middle <= CONTROL_MIDDLE_8:
        return (f"beats control on the full ladder but NOT on the middle eight "
                f"({middle:+.3f} vs {CONTROL_MIDDLE_8:+.3f}) -- concentration")
    if desized is None:
        return "CLEARS CONTROL on both -- de-sized run still required"
    dm = desized["monotonicity"]
    if dm != dm or dm <= 0.5:
        return (f"clears control but COLLAPSES de-sized ({dm:+.3f}) -- it was size")
    return (f"CLEARS CONTROL on both AND survives de-sizing ({dm:+.3f}) -- "
            "the first candidate in this project to do so; retest on our own panel")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credentials", type=Path,
                        default=Path.home() / ".worldquant_brain.json")
    parser.add_argument("--group", default="sector")
    parser.add_argument("--neutralization", default="MARKET",
                        help="MARKET matches how the control was measured (+0.867)")
    parser.add_argument("--candidates", nargs="*", default=list(CANDIDATES))
    parser.add_argument("--skip-desize-control", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "evidence/worldquant_brain_search_v1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    session = L.login(args.credentials)
    results: dict[str, dict] = {}

    print(f"scored against control_size: monotonicity {CONTROL_MONOTONICITY:+.3f}, "
          f"middle-8 {CONTROL_MIDDLE_8:+.3f}\n"
          f"neutralization {args.neutralization}\n", flush=True)

    if not args.skip_desize_control:
        print("=== validating the de-sizing method (de-sized control must go FLAT) ===",
              flush=True)
        shape = ladder(session, DESIZE_CONTROL.format(g=args.group),
                       args.neutralization, args.group)
        results["_desize_control"] = shape
        flat = not (shape["monotonicity"] > 0.5) or shape["monotonicity"] != shape["monotonicity"]
        print(f"  de-sized control monotonicity {shape['monotonicity']:+.3f}  "
              f"-> {'FLAT, de-sizing works' if flat else 'NOT FLAT -- de-sizing is BROKEN'}",
              flush=True)
        (args.output / "search.json").write_text(json.dumps(results, indent=2, sort_keys=True))
        if not flat:
            print("\nSTOPPING: a de-sized no-skill control still orders itself, so the "
                  "de-sizing does not remove size and no de-sized number below would be "
                  "readable. Fix the method before searching.", flush=True)
            return 1

    for name in args.candidates:
        if name not in CANDIDATES:
            print(f"unknown candidate {name!r}", file=sys.stderr)
            return 2
        expression = CANDIDATES[name]
        print(f"\n=== {name} ===\n  {expression}", flush=True)

        print("  raw:", flush=True)
        raw = ladder(session, expression, args.neutralization, args.group)
        desized = None
        # Only spend the de-sized ladder on something that cleared the control -- 10 more
        # simulations each is the budget, and a candidate below the control is already closed.
        if raw["monotonicity"] == raw["monotonicity"] and raw["monotonicity"] > CONTROL_MONOTONICITY:
            print("  cleared the control -- running DE-SIZED:", flush=True)
            desized = ladder(session, DESIZE.format(x=expression, g=args.group),
                             args.neutralization, args.group)

        results[name] = {"expression": expression, "raw": raw, "desized": desized,
                         "verdict": verdict_against_control(raw, desized)}
        print(f"  monotonicity {raw['monotonicity']:+.3f}  middle-8 "
              f"{raw['monotonicity_middle_8']:+.3f}  d10-d1 {raw['top_minus_bottom']:+.4f}  "
              f"distinct {raw['distinct_values']}/10", flush=True)
        print(f"  {results[name]['verdict']}", flush=True)
        (args.output / "search.json").write_text(json.dumps(results, indent=2, sort_keys=True))

    print("\n" + "=" * 78)
    print("SUMMARY -- scored against a no-skill size control, not against 0.5")
    print("=" * 78)
    for name, row in results.items():
        if name.startswith("_"):
            continue
        print(f"{name:26} {row['raw']['monotonicity']:+7.3f}   {row['verdict'][:88]}")
    print("\nNothing here authorizes a submission. A pass is a hypothesis to rebuild and")
    print("retest on our own panel, because BRAIN's data never leaves the platform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
