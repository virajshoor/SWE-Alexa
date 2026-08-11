# SWE-Alexa

Evaluate **Alexa-Rufus-1** (Amazon.com Alexa for Shopping / Rufus web UI) on **SWE-bench Verified** and **GPQA Diamond** by driving the chat with Playwright.

## System name: **Alexa-Rufus-1**

Use this string as `model_name` / `model_name_or_path` / `system_name` in preds and summaries.

## SWE-bench Verified (`results/run40_live`)

| Metric | Value |
| --- | --- |
| System | **Alexa-Rufus-1** |
| Dataset | `princeton-nlp/SWE-bench_Verified` (first 40 test instances) |
| Interface | amazon.com Alexa for Shopping (`#nav-rufus-disco` / `#rufus-text-area`) |
| Auth | Signed-in US session (cookie jar reused; minimal logins) |
| Parallel workers | **2** |
| Instances completed | **40 / 40** |
| Chat replies captured | **40 / 40** |
| Non-empty patches | **0** |
| Offline resolved estimate | **0%** |

**Headline:** Alexa-Rufus-1 refused software-engineering / GitHub-patch help and steered back to shopping. No unified diffs → **0%** on this 40-instance slice.

## GPQA Diamond (`results/gpqa_diamond_merged`)

| Metric | Value |
| --- | --- |
| System | **Alexa-Rufus-1** |
| Dataset | GPQA Diamond (198 items) |
| Replies / parsed letters | **198 / 198** |
| Correct | **76** |
| Accuracy | **38.4%** |

## Non-code suite (Alexa-Rufus-1)

Balanced slices run in order via `python3 -m swe_alexa bench suite` / `scripts/run_noncode_suite.py`:

| Benchmark | n | Notes |
| --- | --- | --- |
| MMLU-Pro | 80 | 4-option MC |
| ARC-Challenge | 80 | science MC |
| OpenBookQA | 80 | science MC |
| GSM8K | 80 | numeric short answer |
| TruthfulQA-MC | 80 | truthfulness MC |
| SimpleQA | 60 | short factual |
| Shopping-MC | 40 | Amazon/shopping knowledge |

Aggregate: `results/noncode_suite_summary.json`. Per-bench dirs under `results/<name>/`.

See [RESULTS_DETAILED.md](RESULTS_DETAILED.md) for methodology, probe notes, and per-instance IDs.

## Setup

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
export AMAZON_EMAIL='...'
export AMAZON_PASSWORD='...'
# Email OTP once if challenged:
export AMAZON_OTP_CODE='......'
```

## Commands

```bash
# Finish OTP on an open challenge (no extra password login)
PYTHONPATH=. python3 scripts/submit_otp_only.py

# Or full bootstrap
PYTHONPATH=. python3 -m swe_alexa bootstrap --storage artifacts/amazon_storage.json

# Run ≥40 Verified instances in parallel (reuses cookie jar; avoids re-login)
PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 2 --wait 55 \
  --out results/run40_live --storage artifacts/amazon_storage.json

# Non-code suite (MMLU-Pro → … → Shopping-MC)
PYTHONPATH=. python3 scripts/run_noncode_suite.py --workers 2 --wait 45
# Or one benchmark:
PYTHONPATH=. python3 -m swe_alexa bench mmlu_pro --limit 80 --workers 2
```

## Repo layout

| Path | Purpose |
| --- | --- |
| `swe_alexa/` | Playwright Alexa/Rufus client, prompts, patch extractor, parallel runner, grader |
| `scripts/` | Probes + OTP helpers |
| `results/run40_live/` | Live SWE-bench 40-instance preds/trajectories (Alexa-Rufus-1) |
| `results/gpqa_diamond_merged/` | Full GPQA Diamond preds/summary (Alexa-Rufus-1) |
| `RESULTS_DETAILED.md` | Full write-up |
| `PROBE_REPORT.md` | amazon.com discovery notes |

## Limitations

1. Rufus composer `maxlength=500` → prompts are compacted.
2. Alexa for Shopping is a **shopping** assistant; coding refusal is expected and was observed live.
3. Official Docker SWE-bench harness may be unavailable in some VMs; empty-patch sets grade as 0% offline.
