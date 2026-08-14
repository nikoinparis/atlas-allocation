#!/usr/bin/env python3
"""Ingest a vendor export described by a JSON descriptor into the vintage store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("descriptor", type=Path, help="JSON descriptor containing a files mapping")
    parser.add_argument("--store", type=Path, default=ROOT / "data/vintages")
    args = parser.parse_args()
    descriptor_path = args.descriptor.resolve()
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    file_mapping = descriptor.pop("files")
    files = {logical: (descriptor_path.parent / relative).resolve() for logical, relative in file_mapping.items()}
    manifest = SnapshotStore(args.store).ingest(files, descriptor)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
