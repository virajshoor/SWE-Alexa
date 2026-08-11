#!/usr/bin/env python3
"""CLI for SWE-Alexa: probe / bootstrap / run / grade."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running without install
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swe_alexa.evaluate import grade
from swe_alexa.gpqa import run_gpqa
from swe_alexa.runner import bootstrap_session, run_parallel


def main() -> None:
    p = argparse.ArgumentParser(
        description="Evaluate Amazon Alexa for Shopping web UI on SWE-bench / GPQA"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap", help="Login + open Alexa chat once")
    b.add_argument("--storage", default="artifacts/amazon_storage.json")
    b.add_argument("--headed", action="store_true")

    r = sub.add_parser("run", help="Run SWE-bench Verified instances in parallel")
    r.add_argument("--limit", type=int, default=40)
    r.add_argument("--offset", type=int, default=0)
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--wait", type=float, default=45.0)
    r.add_argument("--out", default="results/run")
    r.add_argument("--storage", default="artifacts/amazon_storage.json")
    r.add_argument("--local-json", default="data/verified_50.json")
    r.add_argument("--headed", action="store_true")
    r.add_argument("--model-name", default="Alexa-Rufus-1")

    g = sub.add_parser("grade", help="Grade SWE-bench preds.jsonl")
    g.add_argument("--preds", required=True)
    g.add_argument("--out", default="results/grade")
    g.add_argument("--run-id", default="swe-alexa")

    q = sub.add_parser("gpqa", help="Run GPQA Diamond via Alexa for Shopping web chat")
    q.add_argument("--limit", type=int, default=None, help="Max questions (default: all)")
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--workers", type=int, default=2)
    q.add_argument("--wait", type=float, default=55.0)
    q.add_argument("--out", default="results/gpqa_diamond")
    q.add_argument("--csv", default="data/gpqa_diamond.csv")
    q.add_argument("--storage", default="artifacts/amazon_storage.json")
    q.add_argument("--seed", type=int, default=0)
    q.add_argument("--headed", action="store_true")

    args = p.parse_args()
    if args.cmd == "bootstrap":
        info = bootstrap_session(args.storage, headless=not args.headed)
        print(json.dumps(info, indent=2))
        sys.exit(0 if info.get("alexa_opened") else 2)
    if args.cmd == "run":
        summary = run_parallel(
            limit=args.limit,
            offset=args.offset,
            workers=args.workers,
            headless=not args.headed,
            wait_s=args.wait,
            out_dir=args.out,
            model_name=args.model_name,
            local_json=args.local_json,
            storage_state=args.storage,
        )
        print(json.dumps(summary, indent=2))
        grade(summary["preds_path"], Path(args.out) / "grade", run_id=args.model_name)
        return
    if args.cmd == "grade":
        report = grade(args.preds, args.out, run_id=args.run_id)
        print(json.dumps(report, indent=2))
        return
    if args.cmd == "gpqa":
        summary = run_gpqa(
            limit=args.limit,
            offset=args.offset,
            workers=args.workers,
            headless=not args.headed,
            wait_s=args.wait,
            out_dir=args.out,
            csv_path=args.csv,
            storage_state=args.storage,
            seed=args.seed,
        )
        print(json.dumps(summary, indent=2))
        return


if __name__ == "__main__":
    main()
