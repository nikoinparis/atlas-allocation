#!/usr/bin/env python3
"""Flag SEC terminal records that look like reorganisations rather than endings.

Step 215 measured the terminal register at a 4.7% false-positive rate. The names
made the mechanism plain: BlackRock, Bunge, Ferguson, Cedar Fair, Safehold. Each
old CIK genuinely files a completion 8-K and a Form 25 because the old entity's
shares really are delisted, but the economic investment continues in a successor
after a holdco reincorporation, a redomicile or a merger of equals. The register
detects entity termination; a backtest cares about economic termination, and
those are different events.

This does not reverse any removal. Price continuation is its own imperfect
signal: SunPower's Chapter 11 wiped out the old equity while a successor carried
the name forward, so continuing prices can equally mask a total loss. Silently
un-removing on that basis would trade a known bias for an unknown one.

What it does is add a column and a report, so the ambiguity is visible and a
downstream consumer can decide. Nothing changes behaviour unless something asks
for it.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
REGISTERS = [
    ROOT / "evidence/sec_terminal_membership_v1/sec_terminal_membership.csv",
    ROOT / "evidence/sec_broad_terminal_membership_v2/sec_terminal_membership.csv",
]
OUTPUT = ROOT / "evidence/terminal_successor_continuation_v1"
QUIET_WEEKS = 3
MIN_OBSERVATIONS = 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet-weeks", type=int, default=QUIET_WEEKS)
    parser.add_argument("--min-observations", type=int, default=MIN_OBSERVATIONS)
    args = parser.parse_args()

    panel = pd.read_csv(PANEL, index_col=0)
    panel.index = pd.to_datetime(panel.index)

    rows = []
    for register in REGISTERS:
        if not register.exists():
            continue
        frame = pd.read_csv(register, dtype={"cik10": str})
        frame["sec_terminal_date"] = pd.to_datetime(frame.sec_terminal_date, errors="coerce")
        for record in frame.dropna(subset=["sec_terminal_date"]).itertuples(index=False):
            if record.cik10 not in panel.columns:
                continue
            series = panel[record.cik10].dropna()
            after = series[series.index > record.sec_terminal_date + pd.Timedelta(weeks=args.quiet_weeks)]
            continues = bool(len(after) >= args.min_observations and after.nunique() >= args.min_observations)
            rows.append({
                "register": register.parent.name,
                "cik10": record.cik10,
                "company_name": record.company_name,
                "sec_terminal_date": str(record.sec_terminal_date.date()),
                "terminal_reason": getattr(record, "terminal_reason", ""),
                "weekly_observations_after": int(len(after)),
                "distinct_values_after": int(after.nunique()),
                "last_observation": str(after.index[-1].date()) if len(after) else "",
                "probable_successor_continuation": continues,
            })

    table = pd.DataFrame(rows).drop_duplicates("cik10", keep="last")
    # Continuation alone does not say which kind of event happened. A completion 8-K or a
    # Form 25 with prices still trading is consistent with a holdco reincorporation, where
    # the investment survives. A bankruptcy-equity termination with prices still trading is
    # not: that equity was wiped and something else is carrying the identifier, as SunPower
    # and TuSimple both do here. Splitting them is the difference between a usable flag and
    # a list of anomalies.
    bankrupt = table.terminal_reason.astype(str).str.contains("bankrupt", case=False, na=False)
    table["continuation_kind"] = "not_flagged"
    table.loc[table.probable_successor_continuation & ~bankrupt, "continuation_kind"] = "probable_reorganisation"
    table.loc[table.probable_successor_continuation & bankrupt, "continuation_kind"] = "probable_name_reuse_after_wipeout"
    # Only the reorganisation case is a candidate for not being removed from a universe.
    table["safe_to_treat_as_continuing"] = table.continuation_kind.eq("probable_reorganisation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "terminal_continuation_flags.csv", index=False)
    flagged = table[table.probable_successor_continuation]
    payload = {
        "experiment": "terminal_successor_continuation_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule": (f"flagged when an issuer shows at least {args.min_observations} distinct weekly prices "
                 f"more than {args.quiet_weeks} weeks after its confirmed terminal date"),
        "terminal_records_checkable": int(len(table)),
        "flagged_as_probable_continuation": int(len(flagged)),
        "false_positive_rate": round(len(flagged) / max(len(table), 1), 4),
        "by_terminal_reason": flagged.terminal_reason.value_counts().to_dict(),
        "by_continuation_kind": table.continuation_kind.value_counts().to_dict(),
        "safe_to_treat_as_continuing": int(table.safe_to_treat_as_continuing.sum()),
        "changes_behaviour": False,
        "why_not": ("price continuation is itself unreliable: a successor can carry a name forward after the "
                    "old equity is wiped out, as SunPower did. This reports the ambiguity rather than "
                    "resolving it in either direction."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("\nflagged, longest continuation first:")
    print(flagged.nlargest(12, "weekly_observations_after")[
        ["company_name", "sec_terminal_date", "weekly_observations_after", "continuation_kind"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
