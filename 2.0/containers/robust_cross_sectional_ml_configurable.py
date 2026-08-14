#!/usr/bin/env python3
"""Thin entrypoint that makes the frozen Batch 17 engine feature-configurable."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import robust_cross_sectional_ml as engine


def main() -> int:
    try:
        config_path = Path(sys.argv[sys.argv.index("--config") + 1])
    except (ValueError, IndexError) as exc:
        raise SystemExit("--config is required") from exc
    config = json.loads(config_path.read_text(encoding="utf-8"))
    features = tuple(config["features"])
    if not features or len(features) != len(set(features)):
        raise ValueError("features must be a non-empty unique list")
    engine.FEATURES = features
    return engine.main()


if __name__ == "__main__":
    raise SystemExit(main())
