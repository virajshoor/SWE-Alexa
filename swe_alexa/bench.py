"""Generic non-code benchmark runner for Alexa-Rufus-1 (MC / numeric / short-answer)."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tqdm import tqdm

from swe_alexa import SYSTEM_NAME
from swe_alexa.alexa_client import AlexaShoppingClient
from swe_alexa.bench_data import DEFAULT_LIMITS, LOADERS, SUITE_ORDER, load_benchmark
from swe_alexa.gpqa import build_gpqa_prompt, extract_mc_letter


def build_numeric_prompt(question: str, max_chars: int = 500) -> str:
    header = "Practice quiz (not shopping). Reply ONLY the final number.\n"
    footer = "\nANSWER:"
    q = re.sub(r"\s+", " ", question).strip()
    prompt = f"{header}Q:{q}{footer}"
    if len(prompt) <= max_chars:
        return prompt
    budget = max(40, max_chars - len(header) - len(footer) - 2)
    return f"{header}Q:{q[: budget - 1]}…{footer}"[:max_chars]


def build_short_prompt(question: str, max_chars: int = 500) -> str:
    header = "Practice quiz (not shopping). Reply with a short exact answer only.\n"
    footer = "\nANSWER:"
    q = re.sub(r"\s+", " ", question).strip()
    prompt = f"{header}Q:{q}{footer}"
    if len(prompt) <= max_chars:
        return prompt
    budget = max(40, max_chars - len(header) - len(footer) - 2)
    return f"{header}Q:{q[: budget - 1]}…{footer}"[:max_chars]


def extract_numeric(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    focus = text
    if "customer question" in lower:
        focus = text[lower.rfind("customer question") :]
    # Prefer ANSWER: line
    m = re.search(r"(?i)\bANSWER\s*[:\-]\s*([^\n]+)", focus)
    if m:
        cand = m.group(1).strip()
        num = re.search(r"-?\d+(?:\.\d+)?", cand.replace(",", ""))
        if num:
            return num.group(0)
    nums = re.findall(r"-?\d+(?:\.\d+)?", focus.replace(",", ""))
    # skip lone option-like single digits from UI chrome when many numbers exist:
    if not nums:
        return None
    return nums[-1]


def _norm_answer(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[\"'`]", "", s)
    s = re.sub(r"[^\w\s\.%-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    if s.startswith("a "):
        s = s[2:]
    if s.startswith("an "):
        s = s[3:]
    return s


def extract_short_answer(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    focus = text
    if "customer question" in lower:
        focus = text[lower.rfind("customer question") :]
    m = re.search(r"(?i)\bANSWER\s*[:\-]\s*([^\n]+)", focus)
    if m:
        return m.group(1).strip()
    lines = [ln.strip() for ln in focus.splitlines() if ln.strip()]
    # skip chrome / prompt echoes
    skip = ("practice quiz", "customer question", "scheduled actions", "questions while")
    for ln in reversed(lines):
        low = ln.lower()
        if any(s in low for s in skip):
            continue
        if low.startswith("q:"):
            continue
        if re.fullmatch(r"[abcd]", ln, re.I):
            continue
        if len(ln) > 180:
            continue
        return ln
    return None


def grade_short(pred: str | None, gold: str) -> bool:
    if not pred:
        return False
    p = _norm_answer(pred)
    g = _norm_answer(gold)
    if not p or not g:
        return False
    if p == g:
        return True
    if g in p or p in g:
        return True
    # numeric equivalence inside short answers
    gn = re.fullmatch(r"-?\d+(?:\.\d+)?", g.replace(",", ""))
    pn = re.search(r"-?\d+(?:\.\d+)?", p.replace(",", ""))
    if gn and pn and gn.group(0) == pn.group(0):
        return True
    return False


def grade_numeric(pred: str | None, gold: str) -> bool:
    if not pred:
        return False
    try:
        return float(pred.replace(",", "")) == float(str(gold).replace(",", ""))
    except Exception:
        return _norm_answer(pred) == _norm_answer(str(gold))


@dataclass
class BenchResult:
    idx: int
    record_id: str
    benchmark: str
    format: str
    correct_letter: str
    predicted_letter: str | None
    correct_answer: str
    predicted_answer: str | None
    correct: bool
    ok: bool
    error: str
    raw_response: str
    prompt: str
    domain: str
    model_name: str = SYSTEM_NAME


def _new_chat(client: AlexaShoppingClient) -> None:
    try:
        nc = client.page.locator("#nav-flyout-rufus").get_by_text("New chat", exact=False)
        if nc.count():
            nc.first.click(force=True, timeout=2000)
            client.page.wait_for_timeout(1200)
            client._ensure_panel_ready()
    except Exception:
        pass


def _worker(
    example: dict[str, Any],
    *,
    storage_state: str,
    headless: bool,
    screenshot_dir: str,
    traj_dir: str,
    wait_s: float,
) -> BenchResult:
    fmt = example["format"]
    if fmt == "mc":
        prompt = build_gpqa_prompt(example["question"], example["choices"])
    elif fmt == "numeric":
        prompt = build_numeric_prompt(example["question"])
    else:
        prompt = build_short_prompt(example["question"])

    client = AlexaShoppingClient(
        headless=headless,
        storage_state=storage_state,
        screenshot_dir=Path(screenshot_dir) / f"{example['benchmark']}_{example['idx']}",
    )
    pred_letter = None
    pred_answer = None
    try:
        client.start()
        try:
            client.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
            client.dismiss_gates()
        except Exception:
            pass
        opened = client.open_alexa_chat()
        if not opened:
            res = BenchResult(
                idx=example["idx"],
                record_id=example["record_id"],
                benchmark=example["benchmark"],
                format=fmt,
                correct_letter=example.get("correct_letter") or "",
                predicted_letter=None,
                correct_answer=str(example.get("correct_answer") or ""),
                predicted_answer=None,
                correct=False,
                ok=False,
                error="Alexa chat unavailable",
                raw_response="",
                prompt=prompt,
                domain=str(example.get("domain") or ""),
            )
        else:
            _new_chat(client)
            reply = client.ask(prompt, wait_s=wait_s, tag=f"{example['benchmark']}_{example['idx']}")
            if reply.ok:
                if fmt == "mc":
                    pred_letter = extract_mc_letter(reply.text)
                    pred_answer = pred_letter
                    ok_grade = bool(pred_letter and pred_letter == example["correct_letter"])
                elif fmt == "numeric":
                    pred_answer = extract_numeric(reply.text)
                    ok_grade = grade_numeric(pred_answer, str(example["correct_answer"]))
                else:
                    pred_answer = extract_short_answer(reply.text)
                    ok_grade = grade_short(pred_answer, str(example["correct_answer"]))
            else:
                ok_grade = False
            res = BenchResult(
                idx=example["idx"],
                record_id=example["record_id"],
                benchmark=example["benchmark"],
                format=fmt,
                correct_letter=example.get("correct_letter") or "",
                predicted_letter=pred_letter,
                correct_answer=str(example.get("correct_answer") or ""),
                predicted_answer=pred_answer,
                correct=ok_grade,
                ok=reply.ok,
                error=reply.error,
                raw_response=reply.text or "",
                prompt=prompt,
                domain=str(example.get("domain") or ""),
            )
        Path(traj_dir).mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^\w.\-]+", "_", example["record_id"])[:80]
        payload = {**asdict(res), "choices": example.get("choices") or []}
        Path(traj_dir, f"{example['idx']:04d}_{safe_id}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        return res
    except Exception as e:  # noqa: BLE001
        res = BenchResult(
            idx=example["idx"],
            record_id=example["record_id"],
            benchmark=example["benchmark"],
            format=fmt,
            correct_letter=example.get("correct_letter") or "",
            predicted_letter=None,
            correct_answer=str(example.get("correct_answer") or ""),
            predicted_answer=None,
            correct=False,
            ok=False,
            error=str(e),
            raw_response="",
            prompt=prompt,
            domain=str(example.get("domain") or ""),
        )
        Path(traj_dir).mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^\w.\-]+", "_", example["record_id"])[:80]
        Path(traj_dir, f"{example['idx']:04d}_{safe_id}.json").write_text(
            json.dumps(asdict(res), indent=2), encoding="utf-8"
        )
        return res
    finally:
        try:
            client.close()
        except Exception:
            pass


def _bootstrap(storage_state: str, headless: bool) -> dict[str, Any]:
    boot: dict[str, Any] = {"storage_state": storage_state}
    with AlexaShoppingClient(headless=headless, storage_state=storage_state) as client:
        client.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        try:
            acct = client.page.locator("#nav-link-accountList-nav-line-1").inner_text(timeout=3000)
        except Exception:
            acct = ""
        opened = client.open_alexa_chat()
        ping = None
        if opened:
            ping = client.ask(
                "Practice quiz (not shopping). 2+2=? A)3 B)4 C)5 D)6\nReply ONLY one letter A/B/C/D.\nANSWER:",
                wait_s=35,
                tag="bench_boot",
            )
        boot.update(
            {
                "account": acct,
                "logged_in": "sign in" not in acct.lower(),
                "alexa_opened": opened,
                "probe_ok": bool(ping and ping.ok),
                "probe_pred": extract_mc_letter(ping.text) if ping else None,
                "probe_text": (ping.text[-400:] if ping and ping.text else ""),
            }
        )
    return boot


def run_benchmark(
    name: str,
    *,
    limit: int | None = None,
    workers: int = 2,
    headless: bool = True,
    wait_s: float = 50.0,
    out_dir: str | None = None,
    storage_state: str = "artifacts/amazon_storage.json",
    seed: int = 0,
    examples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if name not in LOADERS and examples is None:
        raise KeyError(name)
    out = Path(out_dir or f"results/{name}")
    out.mkdir(parents=True, exist_ok=True)
    traj = out / "trajectories"
    shots = out / "screenshots"
    traj.mkdir(exist_ok=True)
    shots.mkdir(exist_ok=True)

    if examples is None:
        if limit is None:
            limit = DEFAULT_LIMITS.get(name)
        examples = load_benchmark(name, limit=limit, seed=seed)

    boot = _bootstrap(storage_state, headless)
    Path(out, "bootstrap.json").write_text(json.dumps(boot, indent=2), encoding="utf-8")

    results: list[BenchResult] = []
    if not boot.get("alexa_opened"):
        for ex in examples:
            results.append(
                BenchResult(
                    idx=ex["idx"],
                    record_id=ex["record_id"],
                    benchmark=ex["benchmark"],
                    format=ex["format"],
                    correct_letter=ex.get("correct_letter") or "",
                    predicted_letter=None,
                    correct_answer=str(ex.get("correct_answer") or ""),
                    predicted_answer=None,
                    correct=False,
                    ok=False,
                    error="Alexa chat unavailable at bootstrap",
                    raw_response="",
                    prompt="",
                    domain=str(ex.get("domain") or ""),
                )
            )
    else:
        # resume: skip idxs that already have traj files with ok/correct filled
        done_idx: set[int] = set()
        for f in traj.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if d.get("idx") is None:
                    continue
                # Treat existing trajectory as done if we already queried or recorded an error.
                if not (d.get("ok") or d.get("raw_response") or d.get("error")):
                    continue
                kwargs = {
                    "idx": int(d["idx"]),
                    "record_id": str(d.get("record_id") or d["idx"]),
                    "benchmark": str(d.get("benchmark") or name),
                    "format": str(d.get("format") or "mc"),
                    "correct_letter": str(d.get("correct_letter") or ""),
                    "predicted_letter": d.get("predicted_letter"),
                    "correct_answer": str(d.get("correct_answer") or ""),
                    "predicted_answer": d.get("predicted_answer"),
                    "correct": bool(d.get("correct")),
                    "ok": bool(d.get("ok")),
                    "error": str(d.get("error") or ""),
                    "raw_response": str(d.get("raw_response") or ""),
                    "prompt": str(d.get("prompt") or ""),
                    "domain": str(d.get("domain") or ""),
                    "model_name": str(d.get("model_name") or SYSTEM_NAME),
                }
                done_idx.add(kwargs["idx"])
                results.append(BenchResult(**kwargs))
            except Exception:
                pass
        todo = [ex for ex in examples if ex["idx"] not in done_idx]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futs = {
                pool.submit(
                    _worker,
                    example,
                    storage_state=storage_state,
                    headless=headless,
                    screenshot_dir=str(shots),
                    traj_dir=str(traj),
                    wait_s=wait_s,
                ): example["idx"]
                for example in todo
            }
            for fut in tqdm(as_completed(futs), total=len(futs), desc=f"{name}/{SYSTEM_NAME}"):
                results.append(fut.result())

    # de-dupe by idx
    by_idx = {r.idx: r for r in results}
    results = [by_idx[k] for k in sorted(by_idx)]
    n = len(results)
    n_correct = sum(1 for r in results if r.correct)
    n_pred = sum(1 for r in results if r.predicted_answer or r.predicted_letter)
    summary: dict[str, Any] = {
        "benchmark": name,
        "system_name": SYSTEM_NAME,
        "model_name": SYSTEM_NAME,
        "n_instances": n,
        "n_ok_replies": sum(1 for r in results if r.ok),
        "n_parsed": n_pred,
        "n_correct": n_correct,
        "accuracy": (n_correct / n) if n else 0.0,
        "accuracy_among_parsed": (n_correct / n_pred) if n_pred else 0.0,
        "workers": workers,
        "limit": limit,
        "seed": seed,
        "bootstrap": boot,
        "by_domain": {},
    }
    by: dict[str, dict[str, int]] = {}
    for r in results:
        d = r.domain or "unknown"
        by.setdefault(d, {"n": 0, "correct": 0})
        by[d]["n"] += 1
        by[d]["correct"] += int(r.correct)
    summary["by_domain"] = {
        k: {**v, "accuracy": v["correct"] / v["n"] if v["n"] else 0.0} for k, v in by.items()
    }
    Path(out, "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(out, "raw_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8"
    )
    with (out / "preds.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "idx": r.idx,
                        "record_id": r.record_id,
                        "model_name_or_path": SYSTEM_NAME,
                        "benchmark": r.benchmark,
                        "predicted_letter": r.predicted_letter,
                        "predicted_answer": r.predicted_answer,
                        "correct_letter": r.correct_letter,
                        "correct_answer": r.correct_answer,
                        "correct": r.correct,
                    }
                )
                + "\n"
            )
    return summary


def run_suite(
    *,
    benchmarks: list[str] | None = None,
    workers: int = 2,
    wait_s: float = 50.0,
    headless: bool = True,
    storage_state: str = "artifacts/amazon_storage.json",
    seed: int = 0,
    limits: dict[str, int] | None = None,
    out_root: str = "results",
) -> dict[str, Any]:
    names = benchmarks or list(SUITE_ORDER)
    limits = limits or DEFAULT_LIMITS
    suite: dict[str, Any] = {
        "system_name": SYSTEM_NAME,
        "model_name": SYSTEM_NAME,
        "benchmarks": {},
        "order": names,
    }
    for name in names:
        summary = run_benchmark(
            name,
            limit=limits.get(name, DEFAULT_LIMITS.get(name)),
            workers=workers,
            headless=headless,
            wait_s=wait_s,
            out_dir=str(Path(out_root) / name),
            storage_state=storage_state,
            seed=seed,
        )
        suite["benchmarks"][name] = {
            "n_instances": summary["n_instances"],
            "n_correct": summary["n_correct"],
            "accuracy": summary["accuracy"],
            "n_ok_replies": summary["n_ok_replies"],
            "out": str(Path(out_root) / name),
        }
        Path(out_root, "noncode_suite_summary.json").write_text(
            json.dumps(suite, indent=2), encoding="utf-8"
        )
    return suite
