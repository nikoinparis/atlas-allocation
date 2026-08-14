#!/usr/bin/env python3
"""Build and run the isolated free regime collector using Podman."""

from __future__ import annotations

import argparse
import secrets
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "localhost/po2-regime:1.0"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--google-max-attempts", type=int, default=3)
    parser.add_argument("--google-pause-seconds", type=int, default=15)
    args = parser.parse_args()
    target = ROOT / f"regime-snapshot.{secrets.token_hex(3)}"
    target.mkdir(mode=0o777)
    run(["podman", "build", "-f", "containers/Containerfile.regime", "-t", IMAGE, "."])
    run([
        "podman", "run", "--rm", "-v", f"{target}:/export", IMAGE,
        "--end", args.end,
        "--google-max-attempts", str(args.google_max_attempts),
        "--google-pause-seconds", str(args.google_pause_seconds),
    ])
    print(f"Acquisition saved at {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
