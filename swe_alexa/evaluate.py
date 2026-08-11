"""Grade SWE-bench predictions (cloud sb-cli preferred; local/offline fallback)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def offline_grade(preds_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    """Lightweight grade when Docker harness is unavailable.

    Official resolution requires the SWE-bench Docker harness. This fallback
    reports patch presence / emptiness only and must not be compared to
    leaderboard % resolved.
    """
    preds_path = Path(preds_path)
    rows = []
    for line in preds_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    nonempty = [r for r in rows if (r.get("model_patch") or "").strip()]
    report = {
        "grader": "offline_patch_presence",
        "note": (
            "Full SWE-bench resolution requires Docker test execution. "
            "This offline report only checks whether a non-empty patch was produced."
        ),
        "total": len(rows),
        "nonempty_patches": len(nonempty),
        "empty_patches": len(rows) - len(nonempty),
        "resolved_estimate": 0,
        "resolved_ids": [],
        "nonempty_ids": [r["instance_id"] for r in nonempty],
        "empty_ids": [r["instance_id"] for r in rows if not (r.get("model_patch") or "").strip()],
    }
    Path(out_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def try_sb_cli(preds_path: str | Path, run_id: str) -> dict[str, Any] | None:
    preds_path = Path(preds_path)
    try:
        proc = subprocess.run(
            [
                "sb-cli",
                "submit",
                "swe-bench_verified",
                "test",
                "--predictions_path",
                str(preds_path),
                "--run_id",
                run_id,
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "grader": "sb-cli",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"grader": "sb-cli", "error": str(e)}


def try_local_harness(preds_path: str | Path, run_id: str, max_workers: int = 2) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "swebench.harness.run_evaluation",
                "--dataset_name",
                "princeton-nlp/SWE-bench_Verified",
                "--predictions_path",
                str(preds_path),
                "--max_workers",
                str(max_workers),
                "--run_id",
                run_id,
            ],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        return {
            "grader": "swebench.harness",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"grader": "swebench.harness", "error": str(e)}


def grade(preds_path: str | Path, out_dir: str | Path, run_id: str = "swe-alexa") -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    offline = offline_grade(preds_path, out_dir / "offline_grade.json")
    report: dict[str, Any] = {"offline": offline}
    sb = try_sb_cli(preds_path, run_id=run_id)
    if sb is not None:
        report["sb_cli"] = sb
        Path(out_dir, "sb_cli.json").write_text(json.dumps(sb, indent=2), encoding="utf-8")
    local = try_local_harness(preds_path, run_id=run_id)
    if local is not None:
        report["local_harness"] = local
        Path(out_dir, "local_harness.json").write_text(json.dumps(local, indent=2), encoding="utf-8")
    Path(out_dir, "grade_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
