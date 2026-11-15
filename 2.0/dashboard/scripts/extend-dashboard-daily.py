#!/usr/bin/env python3
"""Compatibility entry point: refresh daily activity with the original strategy rules.

Validates current-quarter fundamental inputs and refuses missing held prices.
Never appends or changes a forward evidence log.
"""
from pathlib import Path
import runpy
import subprocess
import sys

if __name__ == "__main__":
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    subprocess.run([sys.executable, str(scripts / "prepare_dashboard_fundamentals_v1.py")], check=True)
    runpy.run_path(str(scripts / "build_dashboard_continuation_v1.py"), run_name="__main__")
