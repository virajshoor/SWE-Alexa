#!/usr/bin/env python3
"""Merge GPQA part runs into results/gpqa_diamond_merged and print summary."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    ROOT / "results" / "gpqa_diamond",
    ROOT / "results" / "gpqa_diamond_part2",
]
OUT = ROOT / "results" / "gpqa_diamond_merged"


def main() -> None:
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    traj_out = OUT / "trajectories"
    traj_out.mkdir(exist_ok=True)
    for part in PARTS:
        tdir = part / "trajectories"
        if not tdir.exists():
            continue
        for f in sorted(tdir.glob("*.json")):
            rows.append(json.loads(f.read_text(encoding="utf-8")))
            shutil.copy2(f, traj_out / f.name)
    # de-dupe by idx keep last
    by_idx = {}
    for r in rows:
        by_idx[r["idx"]] = r
    results = [by_idx[k] for k in sorted(by_idx)]
    n = len(results)
    n_correct = sum(1 for r in results if r.get("correct"))
    n_pred = sum(1 for r in results if r.get("predicted_letter"))
    summary = {
        "benchmark": "GPQA-Diamond",
        "n_instances": n,
        "n_ok_replies": sum(1 for r in results if r.get("ok")),
        "n_parsed_letters": n_pred,
        "n_correct": n_correct,
        "accuracy": (n_correct / n) if n else 0.0,
        "accuracy_among_parsed": (n_correct / n_pred) if n_pred else 0.0,
        "idxs": [r["idx"] for r in results],
    }
    by = {}
    for r in results:
        d = r.get("domain") or "unknown"
        by.setdefault(d, {"n": 0, "correct": 0})
        by[d]["n"] += 1
        by[d]["correct"] += int(bool(r.get("correct")))
    summary["by_domain"] = {
        k: {**v, "accuracy": v["correct"] / v["n"] if v["n"] else 0.0} for k, v in by.items()
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "raw_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (OUT / "preds.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "idx": r["idx"],
                        "record_id": r.get("record_id"),
                        "predicted_letter": r.get("predicted_letter"),
                        "correct_letter": r.get("correct_letter"),
                        "correct": r.get("correct"),
                    }
                )
                + "\n"
            )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
