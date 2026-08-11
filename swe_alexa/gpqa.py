"""GPQA Diamond evaluation via Alexa for Shopping web chat."""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from swe_alexa.alexa_client import AlexaShoppingClient
from . import SYSTEM_NAME

GPQA_CSV_DEFAULT = "data/gpqa_diamond.csv"
ANSWER_PATTERNS = [
    re.compile(r"(?i)\bANSWER\s*[:\-]\s*([ABCD])\b"),
    re.compile(r"(?i)\b(?:the\s+)?(?:correct\s+)?(?:option|answer|letter)\s+is\s*([ABCD])\b"),
    re.compile(r"(?im)^(?:answer\s*)?([ABCD])(?:\s*[.)])?\s*$"),
]


def load_gpqa(csv_path: str | Path = GPQA_CSV_DEFAULT) -> list[dict[str, Any]]:
    df = pd.read_csv(csv_path)
    rows: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        rows.append(
            {
                "idx": int(i),
                "record_id": str(row.get("Record ID") or i),
                "question": str(row["Question"]),
                "correct_answer": str(row["Correct Answer"]),
                "incorrect_answers": [
                    str(row["Incorrect Answer 1"]),
                    str(row["Incorrect Answer 2"]),
                    str(row["Incorrect Answer 3"]),
                ],
                "subdomain": str(row.get("Subdomain") or ""),
                "domain": str(row.get("High-level domain") or ""),
            }
        )
    return rows


def shuffle_choices(example: dict[str, Any], seed: int) -> tuple[list[str], str]:
    rng = random.Random(seed)
    choices = [example["correct_answer"], *example["incorrect_answers"]]
    order = rng.sample(range(4), 4)
    shuffled = [choices[i] for i in order]
    correct_letter = "ABCD"[shuffled.index(example["correct_answer"])]
    return shuffled, correct_letter


def build_gpqa_prompt(question: str, choices: list[str], max_chars: int = 500) -> str:
    """Fit a multiple-choice item into Rufus maxlength=500."""
    # Prefer compact quiz framing that Alexa answers (validated in probes).
    header = "Practice quiz (not shopping). Reply ONLY one letter A/B/C/D.\n"
    footer = "\nANSWER:"
    # Reserve space for options labels
    labels = "ABCD"
    # Iteratively shrink question and options to fit
    q = " ".join(question.split())
    opts = [re.sub(r"\s+", " ", c).strip() for c in choices]

    def render(qtext: str, o: list[str]) -> str:
        body = "\n".join(f"{L}){t}" for L, t in zip(labels, o))
        return f"{header}Q:{qtext}\n{body}{footer}"

    prompt = render(q, opts)
    if len(prompt) <= max_chars:
        return prompt

    # Shrink options first
    budget = max_chars - len(header) - len(footer) - len(q) - 20
    per = max(12, budget // 4)
    opts2 = [t if len(t) <= per else t[: per - 1] + "…" for t in opts]
    prompt = render(q, opts2)
    if len(prompt) <= max_chars:
        return prompt

    # Then shrink question
    overhead = len(render("", opts2))
    q_budget = max(40, max_chars - overhead)
    q2 = q if len(q) <= q_budget else q[: q_budget - 1] + "…"
    prompt = render(q2, opts2)
    return prompt[:max_chars]


def extract_mc_letter(text: str | None) -> str | None:
    if not text:
        return None
    # Focus on content after the last customer question echo when present
    lower = text.lower()
    focus = text
    if "customer question" in lower:
        focus = text[lower.rfind("customer question") :]
    # Prefer explicit ANSWER: X near the end
    for pat in ANSWER_PATTERNS:
        matches = pat.findall(focus)
        if matches:
            return matches[-1].upper()
    # Standalone letter lines after the prompt
    lines = [ln.strip() for ln in focus.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if re.fullmatch(r"[ABCD]", ln, re.I):
            return ln.upper()
        m = re.fullmatch(r"(?:answer\s*[:\-]?\s*)?([ABCD])(?:\s*[.)].*)?", ln, re.I)
        if m:
            return m.group(1).upper()
    # Last resort: last A-D token that is not part of option listing line like "A)..."
    candidates = []
    for m in re.finditer(r"(?<![A-Za-z])([ABCD])(?![A-Za-z\)])", focus):
        # skip if looks like option header "A)"
        start = m.start()
        window = focus[start : start + 2]
        if window.startswith(tuple(f"{L})" for L in "ABCD")):
            continue
        candidates.append(m.group(1).upper())
    return candidates[-1] if candidates else None


@dataclass
class GPQAResult:
    idx: int
    record_id: str
    correct_letter: str
    predicted_letter: str | None
    correct: bool
    ok: bool
    error: str
    raw_response: str
    prompt: str
    subdomain: str
    domain: str
    model_name: str = SYSTEM_NAME


def _worker(
    example: dict[str, Any],
    *,
    storage_state: str,
    headless: bool,
    screenshot_dir: str,
    traj_dir: str,
    wait_s: float,
    seed: int,
) -> GPQAResult:
    choices, correct = shuffle_choices(example, seed=seed + example["idx"] * 17)
    prompt = build_gpqa_prompt(example["question"], choices)
    client = AlexaShoppingClient(
        headless=headless,
        storage_state=storage_state,
        screenshot_dir=Path(screenshot_dir) / f"gpqa_{example['idx']}",
    )
    try:
        client.start()
        try:
            client.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
            client.dismiss_gates()
        except Exception:
            pass
        opened = client.open_alexa_chat()
        if not opened:
            res = GPQAResult(
                idx=example["idx"],
                record_id=example["record_id"],
                correct_letter=correct,
                predicted_letter=None,
                correct=False,
                ok=False,
                error="Alexa chat unavailable",
                raw_response="",
                prompt=prompt,
                subdomain=example["subdomain"],
                domain=example["domain"],
            )
        else:
            # Fresh chat reduces cross-question contamination
            try:
                nc = client.page.locator("#nav-flyout-rufus").get_by_text("New chat", exact=False)
                if nc.count():
                    nc.first.click(force=True, timeout=2000)
                    client.page.wait_for_timeout(1200)
                    client._ensure_panel_ready()
            except Exception:
                pass
            reply = client.ask(prompt, wait_s=wait_s, tag=f"gpqa_{example['idx']}")
            pred = extract_mc_letter(reply.text) if reply.ok else None
            res = GPQAResult(
                idx=example["idx"],
                record_id=example["record_id"],
                correct_letter=correct,
                predicted_letter=pred,
                correct=bool(pred and pred == correct),
                ok=reply.ok,
                error=reply.error,
                raw_response=reply.text or "",
                prompt=prompt,
                subdomain=example["subdomain"],
                domain=example["domain"],
            )
        Path(traj_dir).mkdir(parents=True, exist_ok=True)
        Path(traj_dir, f"{example['idx']:04d}_{example['record_id']}.json").write_text(
            json.dumps({**asdict(res), "choices": choices}, indent=2),
            encoding="utf-8",
        )
        return res
    except Exception as e:
        return GPQAResult(
            idx=example["idx"],
            record_id=example["record_id"],
            correct_letter=correct,
            predicted_letter=None,
            correct=False,
            ok=False,
            error=str(e),
            raw_response="",
            prompt=prompt,
            subdomain=example["subdomain"],
            domain=example["domain"],
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def run_gpqa(
    *,
    limit: int | None = 40,
    offset: int = 0,
    workers: int = 2,
    headless: bool = True,
    wait_s: float = 55.0,
    out_dir: str = "results/gpqa_diamond",
    csv_path: str = GPQA_CSV_DEFAULT,
    storage_state: str = "artifacts/amazon_storage.json",
    seed: int = 0,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    traj = out / "trajectories"
    shots = out / "screenshots"
    traj.mkdir(exist_ok=True)
    shots.mkdir(exist_ok=True)

    examples = load_gpqa(csv_path)
    if offset:
        examples = examples[offset:]
    if limit is not None:
        examples = examples[:limit]

    # Bootstrap ping with quiz-style prompt
    boot = {"storage_state": storage_state}
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
                wait_s=40,
                tag="gpqa_boot",
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
    Path(out, "bootstrap.json").write_text(json.dumps(boot, indent=2), encoding="utf-8")

    results: list[GPQAResult] = []
    if not boot.get("alexa_opened"):
        for ex in examples:
            choices, correct = shuffle_choices(ex, seed=seed + ex["idx"] * 17)
            prompt = build_gpqa_prompt(ex["question"], choices)
            r = GPQAResult(
                idx=ex["idx"],
                record_id=ex["record_id"],
                correct_letter=correct,
                predicted_letter=None,
                correct=False,
                ok=False,
                error="Alexa chat unavailable at bootstrap",
                raw_response="",
                prompt=prompt,
                subdomain=ex["subdomain"],
                domain=ex["domain"],
            )
            results.append(r)
            Path(traj, f"{ex['idx']:04d}_{ex['record_id']}.json").write_text(
                json.dumps(asdict(r), indent=2), encoding="utf-8"
            )
    else:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {
                ex.submit(
                    _worker,
                    example,
                    storage_state=storage_state,
                    headless=headless,
                    screenshot_dir=str(shots),
                    traj_dir=str(traj),
                    wait_s=wait_s,
                    seed=seed,
                ): example["idx"]
                for example in examples
            }
            for fut in tqdm(as_completed(futs), total=len(futs), desc="GPQA-Alexa"):
                results.append(fut.result())

    results.sort(key=lambda r: r.idx)
    n = len(results)
    n_correct = sum(1 for r in results if r.correct)
    n_pred = sum(1 for r in results if r.predicted_letter)
    summary = {
        "benchmark": "GPQA-Diamond",
        "system_name": SYSTEM_NAME,
        "model_name": SYSTEM_NAME,
        "n_instances": n,
        "n_ok_replies": sum(1 for r in results if r.ok),
        "n_parsed_letters": n_pred,
        "n_correct": n_correct,
        "accuracy": (n_correct / n) if n else 0.0,
        "accuracy_among_parsed": (n_correct / n_pred) if n_pred else 0.0,
        "workers": workers,
        "bootstrap": boot,
        "by_domain": {},
    }
    # domain breakdown
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
    # preds without dumping full gold explanations
    with (out / "preds.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "idx": r.idx,
                        "record_id": r.record_id,
                        "model_name_or_path": SYSTEM_NAME,
                        "predicted_letter": r.predicted_letter,
                        "correct_letter": r.correct_letter,
                        "correct": r.correct,
                    }
                )
                + "\n"
            )
    return summary
