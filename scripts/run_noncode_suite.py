#!/usr/bin/env python3
"""Run non-code Alexa-Rufus-1 suite in order and write aggregate summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swe_alexa.bench import run_suite
from swe_alexa.bench_data import DEFAULT_LIMITS, SUITE_ORDER


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--benchmarks", nargs="*", default=None, help="Subset / override order")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--wait", type=float, default=50.0)
    p.add_argument("--storage", default="artifacts/amazon_storage.json")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-root", default="results")
    p.add_argument("--headed", action="store_true")
    args = p.parse_args()
    names = args.benchmarks or list(SUITE_ORDER)
    print(json.dumps({"system": "Alexa-Rufus-1", "order": names, "limits": DEFAULT_LIMITS}, indent=2))
    suite = run_suite(
        benchmarks=names,
        workers=args.workers,
        wait_s=args.wait,
        headless=not args.headed,
        storage_state=args.storage,
        seed=args.seed,
        out_root=args.out_root,
    )
    print(json.dumps(suite, indent=2))


if __name__ == "__main__":
    main()
