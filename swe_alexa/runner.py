"""Parallel SWE-bench Verified runner against Alexa for Shopping web UI."""

from __future__ import annotations

import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from datasets import load_dataset
from tqdm import tqdm

from swe_alexa.alexa_client import AlexaShoppingClient
from swe_alexa.patch_extract import extract_patch
from swe_alexa.prompts import build_prompt


@dataclass
class InstanceResult:
    instance_id: str
    model_name_or_path: str
    model_patch: str
    raw_response: str
    ok: bool
    error: str
    url: str
    screenshot: str


def load_instances(limit: int = 40, offset: int = 0, local_json: str | None = None) -> list[dict]:
    if local_json and Path(local_json).exists():
        rows = json.loads(Path(local_json).read_text(encoding="utf-8"))
        return rows[offset : offset + limit]
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    rows = []
    for i, row in enumerate(ds):
        if i < offset:
            continue
        if len(rows) >= limit:
            break
        rows.append({k: row[k] for k in row.keys()})
    return rows


def _worker(
    instance: dict,
    *,
    storage_state: str,
    headless: bool,
    screenshot_dir: str,
    traj_dir: str,
    wait_s: float,
    model_name: str,
) -> InstanceResult:
    iid = instance["instance_id"]
    prompt = build_prompt(instance)
    # Each worker gets its own browser; share cookies via storage_state file.
    client = AlexaShoppingClient(
        headless=headless,
        storage_state=storage_state,
        screenshot_dir=Path(screenshot_dir) / iid,
    )
    try:
        client.start()
        # Prefer existing cookie jar; avoid extra password/OTP logins (account flags).
        if os.environ.get("SWE_ALEXA_FORCE_LOGIN", "").lower() in {"1", "true", "yes"}:
            client.login_if_needed()
        else:
            try:
                client.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
                client.dismiss_gates()
            except Exception:
                pass
        opened = client.open_alexa_chat()
        if not opened:
            res = InstanceResult(
                instance_id=iid,
                model_name_or_path=model_name,
                model_patch="",
                raw_response="",
                ok=False,
                error="Alexa chat UI unavailable",
                url=client.page.url,
                screenshot="",
            )
        else:
            reply = client.ask(prompt, wait_s=wait_s, tag=iid.replace("/", "_")[:80])
            patch = extract_patch(reply.text) if reply.ok else ""
            res = InstanceResult(
                instance_id=iid,
                model_name_or_path=model_name,
                model_patch=patch,
                raw_response=reply.text,
                ok=reply.ok,
                error=reply.error,
                url=reply.url,
                screenshot=reply.screenshot,
            )
        Path(traj_dir).mkdir(parents=True, exist_ok=True)
        Path(traj_dir, f"{iid}.json").write_text(
            json.dumps({"prompt": prompt, **asdict(res)}, indent=2),
            encoding="utf-8",
        )
        return res
    except Exception as e:
        return InstanceResult(
            instance_id=iid,
            model_name_or_path=model_name,
            model_patch="",
            raw_response="",
            ok=False,
            error=f"{e}\n{traceback.format_exc()}",
            url="",
            screenshot="",
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def bootstrap_session(storage_state: str, headless: bool = True) -> dict[str, Any]:
    """Login once and persist cookies for parallel workers."""
    Path(storage_state).parent.mkdir(parents=True, exist_ok=True)
    with AlexaShoppingClient(headless=headless, storage_state=storage_state) as client:
        ok = client.login_if_needed()
        opened = client.open_alexa_chat() if ok else False
        probe = None
        if opened:
            probe = client.ask(
                "Reply with exactly: PONG",
                wait_s=30,
                tag="bootstrap_ping",
            )
        return {
            "logged_in": ok,
            "alexa_opened": opened,
            "probe_ok": bool(probe and probe.ok),
            "probe_text": (probe.text[:500] if probe else ""),
            "probe_error": (probe.error if probe else "skipped"),
            "storage_state": storage_state,
            "has_email": bool(os.environ.get("AMAZON_EMAIL")),
        }


def run_parallel(
    *,
    limit: int = 40,
    offset: int = 0,
    workers: int = 4,
    headless: bool = True,
    wait_s: float = 45.0,
    out_dir: str = "results",
    model_name: str = "amazon-alexa-for-shopping-web",
    local_json: str | None = "data/verified_50.json",
    storage_state: str = "artifacts/amazon_storage.json",
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    traj_dir = out / "trajectories"
    shot_dir = out / "screenshots"
    traj_dir.mkdir(exist_ok=True)
    shot_dir.mkdir(exist_ok=True)

    boot = bootstrap_session(storage_state, headless=headless)
    Path(out, "bootstrap.json").write_text(json.dumps(boot, indent=2), encoding="utf-8")

    instances = load_instances(limit=limit, offset=offset, local_json=local_json)
    results: list[InstanceResult] = []

    # If Alexa UI is unavailable, still complete all instances with structured failures
    # so the experiment is reproducible and meets the instance count requirement.
    if not boot.get("alexa_opened"):
        for inst in instances:
            r = InstanceResult(
                instance_id=inst["instance_id"],
                model_name_or_path=model_name,
                model_patch="",
                raw_response="",
                ok=False,
                error=(
                    "Alexa for Shopping chat not available without a signed-in amazon.com "
                    "session (or chat failed to open). Set AMAZON_EMAIL / AMAZON_PASSWORD."
                ),
                url="https://www.amazon.com/",
                screenshot="",
            )
            results.append(r)
            Path(traj_dir, f"{inst['instance_id']}.json").write_text(
                json.dumps({"prompt": build_prompt(inst), **asdict(r)}, indent=2),
                encoding="utf-8",
            )
    else:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {
                ex.submit(
                    _worker,
                    inst,
                    storage_state=storage_state,
                    headless=headless,
                    screenshot_dir=str(shot_dir),
                    traj_dir=str(traj_dir),
                    wait_s=wait_s,
                    model_name=model_name,
                ): inst["instance_id"]
                for inst in instances
            }
            for fut in tqdm(as_completed(futs), total=len(futs), desc="SWE-Alexa"):
                results.append(fut.result())

    results.sort(key=lambda r: r.instance_id)
    preds_path = out / "preds.jsonl"
    with preds_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "instance_id": r.instance_id,
                        "model_name_or_path": r.model_name_or_path,
                        "model_patch": r.model_patch,
                    }
                )
                + "\n"
            )

    summary = {
        "n_instances": len(results),
        "n_ok_replies": sum(1 for r in results if r.ok),
        "n_nonempty_patches": sum(1 for r in results if r.model_patch.strip()),
        "n_errors": sum(1 for r in results if r.error),
        "bootstrap": boot,
        "preds_path": str(preds_path),
        "model_name": model_name,
        "workers": workers,
        "instance_ids": [r.instance_id for r in results],
    }
    Path(out, "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(out, "raw_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    return summary
